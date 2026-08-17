from __future__ import annotations

from datetime import datetime, timezone

from .config import OptimizerSettings
from .models import IntentArtifact, IntentAsset
from .optimizer import StrategySnapshot, normalize_weights_to_bps


def build_intent_artifact(
    snapshot: StrategySnapshot,
    *,
    epoch: int,
    expiry: int,
    settings: OptimizerSettings | None = None,
    created_at: str | None = None,
) -> IntentArtifact:
    settings = settings or OptimizerSettings()
    normalized_bps = normalize_weights_to_bps(snapshot.weights)
    created_at = created_at or datetime.now(timezone.utc).isoformat()

    assets: list[IntentAsset] = []
    for asset_name, ticker in settings.tickers.items():
        if asset_name not in snapshot.weights:
            raise ValueError(f"Missing weight for asset '{asset_name}'.")
        assets.append(
            IntentAsset(
                name=asset_name,
                ticker=ticker,
                address=settings.asset_addresses[asset_name],
                weight=float(snapshot.weights[asset_name]),
                target_bps=normalized_bps[asset_name],
            )
        )

    artifact = IntentArtifact(
        intent_version="1.0.0",
        epoch=epoch,
        strategy=snapshot.strategy,
        source_mode=snapshot.source_mode,
        weights_mode=snapshot.weights_mode,
        as_of=snapshot.as_of,
        expiry=expiry,
        created_at=created_at,
        source_window=snapshot.source_window,
        assets=assets,
        metrics=snapshot.metrics,
        extra={
            "transactionCostBps": settings.transaction_cost_bps,
            "minWeight": settings.base_min_weight,
            "maxWeight": settings.base_max_weight,
        },
    )
    artifact.compute_hashes()
    return artifact
