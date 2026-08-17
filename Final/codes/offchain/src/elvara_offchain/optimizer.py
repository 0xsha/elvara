from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yfinance as yf

from .config import OptimizerSettings
from .models import StrategyMetrics, SourceWindow
from .sample_data import SAMPLE_SOURCE_WINDOW, SAMPLE_STRATEGIES


SUPPORTED_STRATEGIES = (
    "CVaR",
    "Semi-Var",
    "Variance",
    "EVaR",
    "Worst",
    "Max DD",
    "Equal Weight",
)


@dataclass(slots=True)
class ResearchDataset:
    prices: pd.DataFrame
    returns: pd.DataFrame
    tbill_daily: pd.Series
    folds: list[tuple[slice, slice]]
    source_window: SourceWindow


@dataclass(slots=True)
class StrategySnapshot:
    strategy: str
    source_mode: str
    weights_mode: str
    as_of: str
    source_window: SourceWindow
    weights: dict[str, float]
    metrics: StrategyMetrics


def walk_forward_slices(
    index: pd.Index,
    min_train_days: int,
    test_days: int,
    step_days: int | None = None,
) -> list[tuple[slice, slice]]:
    step_days = test_days if step_days is None else step_days
    folds: list[tuple[slice, slice]] = []
    train_end = min_train_days

    while train_end + test_days <= len(index):
        folds.append((slice(0, train_end), slice(train_end, train_end + test_days)))
        train_end += step_days

    return folds


def compute_train_risk_free_rate(
    tbill_daily: pd.Series,
    train_index: pd.Index,
) -> float:
    aligned = tbill_daily.reindex(train_index).ffill().dropna()
    return float(aligned.mean()) if not aligned.empty else 0.0


def apply_rebalance_cost(
    returns: pd.Series,
    turnover: float,
    cost_rate: float,
) -> tuple[pd.Series, float]:
    adjusted = returns.copy()
    cost = float(turnover * cost_rate)
    if not adjusted.empty and cost > 0:
        adjusted.iloc[0] = (1 - cost) * (1 + adjusted.iloc[0]) - 1
    return adjusted, cost


def compute_end_weights(asset_returns: pd.DataFrame, start_weights: np.ndarray) -> np.ndarray:
    gross_returns = (1 + asset_returns).prod(axis=0).to_numpy(dtype=float)
    end_values = np.asarray(start_weights, dtype=float) * gross_returns
    total = float(end_values.sum())
    if total <= 0:
        return np.asarray(start_weights, dtype=float)
    return end_values / total


def _price_frame(raw_prices: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    if isinstance(raw_prices.columns, pd.MultiIndex):
        price_field = (
            "Adj Close"
            if "Adj Close" in raw_prices.columns.get_level_values(0)
            else "Close"
        )
        return raw_prices[price_field][tickers].copy()

    if "Adj Close" in raw_prices.columns:
        return raw_prices[["Adj Close"]].rename(columns={"Adj Close": tickers[0]}).copy()
    if "Close" in raw_prices.columns:
        return raw_prices[["Close"]].rename(columns={"Close": tickers[0]}).copy()
    raise ValueError("Price download did not include a Close or Adj Close column.")


def fetch_research_dataset(settings: OptimizerSettings | None = None) -> ResearchDataset:
    settings = settings or OptimizerSettings()
    tickers = list(settings.tickers.values())
    asset_names = list(settings.tickers.keys())

    raw_prices = yf.download(
        tickers,
        start=settings.start_date,
        end=settings.end_date,
        auto_adjust=False,
        progress=False,
    )
    if raw_prices.empty:
        raise ValueError("Price download returned no rows for the configured assets.")

    prices = _price_frame(raw_prices, tickers)
    prices.columns = asset_names
    prices = prices.dropna()

    from skfolio.preprocessing import prices_to_returns

    returns = prices_to_returns(prices)

    tbill = (
        yf.download(
            "^IRX",
            start=settings.start_date,
            end=settings.end_date,
            auto_adjust=False,
            progress=False,
        )["Close"]
        .squeeze()
        .dropna()
    )
    tbill_daily = (tbill / 100) / settings.trading_days

    folds = walk_forward_slices(
        returns.index,
        settings.min_train_days,
        settings.test_days,
        settings.step_days,
    )
    if not folds:
        raise ValueError("Not enough observations for the configured walk-forward settings.")

    oos_start = returns.index[folds[0][1].start]
    oos_end = returns.index[folds[-1][1].stop - 1]
    source_window = SourceWindow(
        start_date=settings.start_date,
        end_date=settings.end_date,
        min_train_days=settings.min_train_days,
        test_days=settings.test_days,
        step_days=settings.step_days,
        oos_start=str(oos_start.date()),
        oos_end=str(oos_end.date()),
    )

    return ResearchDataset(
        prices=prices,
        returns=returns,
        tbill_daily=tbill_daily,
        folds=folds,
        source_window=source_window,
    )


def _strategy_configs() -> dict[str, dict[str, Any]]:
    from skfolio import RiskMeasure

    return {
        "CVaR": {"risk_measure": RiskMeasure.CVAR},
        "Semi-Var": {"risk_measure": RiskMeasure.SEMI_VARIANCE},
        "Variance": {"risk_measure": RiskMeasure.VARIANCE},
        "EVaR": {
            "risk_measure": RiskMeasure.EVAR,
            "solver": "CLARABEL",
            "scale_constraints": 1e-1,
        },
        "Worst": {"risk_measure": RiskMeasure.WORST_REALIZATION},
        "Max DD": {"risk_measure": RiskMeasure.MAX_DRAWDOWN},
    }


def run_walk_forward_strategy(
    dataset: ResearchDataset,
    model_kwargs: Mapping[str, Any],
    settings: OptimizerSettings | None = None,
    *,
    min_weight: float | None = None,
    max_weight: float | None = None,
) -> dict[str, Any]:
    settings = settings or OptimizerSettings()
    min_weight = settings.base_min_weight if min_weight is None else min_weight
    max_weight = settings.base_max_weight if max_weight is None else max_weight

    from skfolio.optimization import MeanRisk, ObjectiveFunction

    oos_returns: list[pd.Series] = []
    rebalance_weights: list[np.ndarray] = []
    current_weights = np.zeros(len(dataset.prices.columns))
    total_cost = 0.0
    fallback_count = 0

    for train_slice, test_slice in dataset.folds:
        x_train = dataset.returns.iloc[train_slice].copy()
        x_test = dataset.returns.iloc[test_slice].copy()
        fold_risk_free_rate = compute_train_risk_free_rate(dataset.tbill_daily, x_train.index)

        try:
            model = MeanRisk(
                objective_function=ObjectiveFunction.MAXIMIZE_RATIO,
                min_weights=min_weight,
                max_weights=max_weight,
                risk_free_rate=fold_risk_free_rate,
                **model_kwargs,
            )
            model.fit(x_train)
            portfolio = model.predict(x_test)
            target_weights = np.asarray(model.weights_, dtype=float)
            fold_returns = pd.Series(portfolio.returns, index=x_test.index)
        except Exception:
            if current_weights.sum() == 0:
                raise
            target_weights = current_weights.copy()
            fold_returns = x_test.mul(target_weights, axis=1).sum(axis=1)
            fallback_count += 1

        turnover = float(np.abs(target_weights - current_weights).sum())
        fold_returns, fold_cost = apply_rebalance_cost(
            fold_returns,
            turnover,
            settings.cost_rate,
        )

        oos_returns.append(fold_returns)
        rebalance_weights.append(target_weights.copy())
        total_cost += fold_cost
        current_weights = compute_end_weights(x_test, target_weights)

    return {
        "returns": pd.concat(oos_returns),
        "avg_weights": pd.Series(
            np.mean(rebalance_weights, axis=0),
            index=dataset.prices.columns,
        ),
        "last_weights": pd.Series(rebalance_weights[-1], index=dataset.prices.columns),
        "total_cost": total_cost,
        "n_rebalances": len(rebalance_weights),
        "fallback_count": fallback_count,
    }


def run_equal_weight_strategy(
    dataset: ResearchDataset,
    settings: OptimizerSettings | None = None,
) -> dict[str, Any]:
    settings = settings or OptimizerSettings()
    target_weights = np.repeat(1 / len(dataset.prices.columns), len(dataset.prices.columns))
    oos_returns: list[pd.Series] = []
    rebalance_weights: list[np.ndarray] = []
    current_weights = np.zeros(len(dataset.prices.columns))
    total_cost = 0.0

    for _, test_slice in dataset.folds:
        x_test = dataset.returns.iloc[test_slice].copy()
        fold_returns = x_test.mul(target_weights, axis=1).sum(axis=1)
        turnover = float(np.abs(target_weights - current_weights).sum())
        fold_returns, fold_cost = apply_rebalance_cost(
            fold_returns,
            turnover,
            settings.cost_rate,
        )

        oos_returns.append(fold_returns)
        rebalance_weights.append(target_weights.copy())
        total_cost += fold_cost
        current_weights = compute_end_weights(x_test, target_weights)

    return {
        "returns": pd.concat(oos_returns),
        "avg_weights": pd.Series(
            np.mean(rebalance_weights, axis=0),
            index=dataset.prices.columns,
        ),
        "last_weights": pd.Series(rebalance_weights[-1], index=dataset.prices.columns),
        "total_cost": total_cost,
        "n_rebalances": len(rebalance_weights),
        "fallback_count": 0,
    }


def build_strategy_stats(
    returns: pd.Series,
    weights: pd.Series,
    total_cost: float,
    reporting_index: pd.Index,
    risk_free_rate: float,
    settings: OptimizerSettings | None = None,
    *,
    fallback_count: int = 0,
    n_rebalances: int = 0,
) -> StrategyMetrics:
    settings = settings or OptimizerSettings()

    returns = pd.Series(returns, index=reporting_index)
    cumulative_returns = (1 + returns).cumprod() - 1
    portfolio_values = settings.initial_value * (1 + cumulative_returns)

    running_peak_value = portfolio_values.cummax().clip(lower=settings.initial_value)
    drawdown = 1 - portfolio_values / running_peak_value

    annualized_mean = float(returns.mean() * settings.trading_days)
    annualized_vol = float(returns.std(ddof=0) * np.sqrt(settings.trading_days))
    downside = returns[returns < 0]
    downside_vol = (
        float(downside.std(ddof=0) * np.sqrt(settings.trading_days))
        if not downside.empty
        else np.nan
    )
    excess_annualized = float((returns.mean() - risk_free_rate) * settings.trading_days)
    sharpe = excess_annualized / annualized_vol if annualized_vol > 0 else np.nan
    sortino = excess_annualized / downside_vol if downside_vol > 0 else np.nan

    return StrategyMetrics(
        final_value=float(portfolio_values.iloc[-1]),
        total_return=float(cumulative_returns.iloc[-1]),
        max_drawdown=float(drawdown.max()),
        max_loss=float((running_peak_value - portfolio_values).max()),
        annualized_mean=annualized_mean,
        sharpe=float(sharpe) if not np.isnan(sharpe) else None,
        sortino=float(sortino) if not np.isnan(sortino) else None,
        cost_drag=float(total_cost),
        fallback_count=fallback_count,
        n_rebalances=n_rebalances,
    )


def normalize_weights_to_bps(weights: Mapping[str, float]) -> dict[str, int]:
    series = pd.Series(weights, dtype=float)
    clipped = series.clip(lower=0)
    total = float(clipped.sum())
    if total <= 0:
        raise ValueError("Weights must sum to a positive value before normalization.")

    normalized = clipped / total
    scaled = normalized * 10_000
    floors = np.floor(scaled).astype(int)
    remainder = 10_000 - int(floors.sum())

    if remainder > 0:
        fractions = scaled - floors
        order = sorted(
            range(len(series.index)),
            key=lambda idx: (-fractions.iloc[idx], str(series.index[idx])),
        )
        for idx in order[:remainder]:
            floors.iloc[idx] += 1

    return {name: int(floors.loc[name]) for name in series.index}


def build_sample_strategy_snapshot(
    strategy_name: str,
) -> StrategySnapshot:
    if strategy_name not in SAMPLE_STRATEGIES:
        raise ValueError(
            f"Unsupported sample strategy '{strategy_name}'. "
            f"Expected one of: {', '.join(SAMPLE_STRATEGIES)}."
        )

    sample = SAMPLE_STRATEGIES[strategy_name]
    metrics = StrategyMetrics(
        final_value=float(sample["final_value"]),
        total_return=float(sample["total_return"]),
        max_drawdown=float(sample["max_drawdown"]),
        max_loss=float(sample["max_loss"]),
        annualized_mean=None,
        sharpe=float(sample["sharpe"]),
        sortino=float(sample["sortino"]),
        cost_drag=float(sample["cost_drag"]),
        fallback_count=int(sample["fallback_count"]),
        n_rebalances=int(sample["n_rebalances"]),
    )

    return StrategySnapshot(
        strategy=strategy_name,
        source_mode="sample",
        weights_mode="avg",
        as_of=SAMPLE_SOURCE_WINDOW.oos_end,
        source_window=SAMPLE_SOURCE_WINDOW,
        weights=dict(sample["weights"]),
        metrics=metrics,
    )


def build_live_strategy_snapshot(
    strategy_name: str,
    settings: OptimizerSettings | None = None,
    *,
    weights_mode: str = "last",
) -> StrategySnapshot:
    settings = settings or OptimizerSettings()
    dataset = fetch_research_dataset(settings)

    if strategy_name == "Equal Weight":
        run = run_equal_weight_strategy(dataset, settings)
    else:
        configs = _strategy_configs()
        if strategy_name not in configs:
            raise ValueError(
                f"Unsupported strategy '{strategy_name}'. "
                f"Expected one of: {', '.join(SUPPORTED_STRATEGIES)}."
            )
        run = run_walk_forward_strategy(dataset, configs[strategy_name], settings)

    oos_tbill = dataset.tbill_daily.reindex(run["returns"].index).ffill().dropna()
    oos_risk_free_rate = float(oos_tbill.mean()) if not oos_tbill.empty else 0.0
    selected_weights = run["last_weights"] if weights_mode == "last" else run["avg_weights"]
    metrics = build_strategy_stats(
        run["returns"],
        selected_weights,
        run["total_cost"],
        reporting_index=run["returns"].index,
        risk_free_rate=oos_risk_free_rate,
        settings=settings,
        fallback_count=run["fallback_count"],
        n_rebalances=run["n_rebalances"],
    )

    return StrategySnapshot(
        strategy=strategy_name,
        source_mode="live",
        weights_mode=weights_mode,
        as_of=dataset.source_window.oos_end,
        source_window=dataset.source_window,
        weights={name: float(value) for name, value in selected_weights.items()},
        metrics=metrics,
    )


def build_strategy_snapshot(
    strategy_name: str,
    settings: OptimizerSettings | None = None,
    *,
    use_sample: bool = False,
    weights_mode: str = "last",
) -> StrategySnapshot:
    if strategy_name not in SUPPORTED_STRATEGIES:
        raise ValueError(
            f"Unsupported strategy '{strategy_name}'. "
            f"Expected one of: {', '.join(SUPPORTED_STRATEGIES)}."
        )

    if use_sample:
        return build_sample_strategy_snapshot(strategy_name)
    return build_live_strategy_snapshot(strategy_name, settings, weights_mode=weights_mode)
