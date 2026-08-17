from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(data: Any) -> str:
    digest = hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
    return f"0x{digest}"


@dataclass(slots=True)
class SourceWindow:
    start_date: str
    end_date: str
    min_train_days: int
    test_days: int
    step_days: int
    oos_start: str
    oos_end: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "startDate": self.start_date,
            "endDate": self.end_date,
            "minTrainDays": self.min_train_days,
            "testDays": self.test_days,
            "stepDays": self.step_days,
            "oosStart": self.oos_start,
            "oosEnd": self.oos_end,
        }


@dataclass(slots=True)
class StrategyMetrics:
    final_value: float | None
    total_return: float | None
    max_drawdown: float | None
    max_loss: float | None
    annualized_mean: float | None
    sharpe: float | None
    sortino: float | None
    cost_drag: float
    fallback_count: int
    n_rebalances: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "finalValue": self.final_value,
            "totalReturn": self.total_return,
            "maxDrawdown": self.max_drawdown,
            "maxLoss": self.max_loss,
            "annualizedMean": self.annualized_mean,
            "sharpe": self.sharpe,
            "sortino": self.sortino,
            "costDrag": self.cost_drag,
            "fallbackCount": self.fallback_count,
            "rebalances": self.n_rebalances,
        }


@dataclass(slots=True)
class IntentAsset:
    name: str
    ticker: str
    address: str
    weight: float
    target_bps: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ticker": self.ticker,
            "address": self.address,
            "weight": self.weight,
            "targetBps": self.target_bps,
        }


@dataclass(slots=True)
class IntentArtifact:
    intent_version: str
    epoch: int
    strategy: str
    source_mode: str
    weights_mode: str
    as_of: str
    expiry: int
    created_at: str
    source_window: SourceWindow
    assets: list[IntentAsset]
    metrics: StrategyMetrics
    weights_hash: str = ""
    metadata_hash: str = ""
    intent_hash: str | None = None
    contract_address: str | None = None
    tx_hash: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def target_bps(self) -> list[int]:
        return [asset.target_bps for asset in self.assets]

    def payload_without_hashes(self) -> dict[str, Any]:
        payload = {
            "intentVersion": self.intent_version,
            "epoch": self.epoch,
            "strategy": self.strategy,
            "sourceMode": self.source_mode,
            "weightsMode": self.weights_mode,
            "asOf": self.as_of,
            "expiry": self.expiry,
            "createdAt": self.created_at,
            "sourceWindow": self.source_window.to_dict(),
            "assets": [asset.to_dict() for asset in self.assets],
            "targetBps": self.target_bps,
            "metrics": self.metrics.to_dict(),
        }
        if self.extra:
            payload["extra"] = self.extra
        return payload

    def compute_hashes(self) -> None:
        weights_payload = [
            {"address": asset.address.lower(), "targetBps": asset.target_bps}
            for asset in self.assets
        ]
        self.weights_hash = sha256_hex(weights_payload)
        metadata_payload = self.payload_without_hashes()
        metadata_payload["weightsHash"] = self.weights_hash
        self.metadata_hash = sha256_hex(metadata_payload)

    def to_dict(self) -> dict[str, Any]:
        payload = self.payload_without_hashes()
        payload["weightsHash"] = self.weights_hash
        payload["metadataHash"] = self.metadata_hash
        if self.intent_hash:
            payload["intentHash"] = self.intent_hash
        if self.contract_address:
            payload["contractAddress"] = self.contract_address
        if self.tx_hash:
            payload["txHash"] = self.tx_hash
        return payload
