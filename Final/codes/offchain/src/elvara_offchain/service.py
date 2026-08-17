from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from time import time
from typing import Any

from .config import OffchainSettings, OptimizerSettings, load_offchain_settings
from .intents import build_intent_artifact
from .optimizer import build_strategy_snapshot
from .relay import PortfolioIntentRegistryRelay, compute_intent_hash
from .sample_data import SAMPLE_CREATED_AT, SAMPLE_EPOCH, SAMPLE_EXPIRY
from .storage import IntentStore


@dataclass(slots=True)
class RunIntentOptions:
    strategy: str = "CVaR"
    epoch: int | None = None
    expiry_seconds: int | None = None
    submit_onchain: bool = False
    use_sample: bool = False
    use_today: bool = False
    weights_mode: str = "last"


class IntentService:
    def __init__(
        self,
        optimizer_settings: OptimizerSettings | None = None,
        offchain_settings: OffchainSettings | None = None,
        store: IntentStore | None = None,
    ) -> None:
        self.optimizer_settings = optimizer_settings or OptimizerSettings()
        self.offchain_settings = offchain_settings or load_offchain_settings()
        self.store = store or IntentStore(self.offchain_settings.db_path)
        self.relay = (
            PortfolioIntentRegistryRelay(self.offchain_settings)
            if self.offchain_settings.relay_enabled
            else None
        )

    def run_rebalance(self, options: RunIntentOptions) -> dict[str, Any]:
        if options.use_today and options.use_sample:
            raise ValueError("--today/useToday cannot be combined with --sample/useSample.")

        if options.use_sample:
            epoch = SAMPLE_EPOCH if options.epoch is None else options.epoch
            expiry = (
                SAMPLE_EXPIRY
                if options.expiry_seconds is None
                else int(time()) + options.expiry_seconds
            )
            created_at = SAMPLE_CREATED_AT
        else:
            epoch = self.store.next_epoch() if options.epoch is None else options.epoch
            expiry_seconds = (
                self.offchain_settings.default_expiry_seconds
                if options.expiry_seconds is None
                else options.expiry_seconds
            )
            expiry = int(time()) + expiry_seconds
            created_at = None

        optimizer_settings = self.optimizer_settings
        if options.use_today:
            optimizer_settings = replace(
                optimizer_settings,
                end_date=date.today().isoformat(),
            )

        snapshot = build_strategy_snapshot(
            options.strategy,
            optimizer_settings,
            use_sample=options.use_sample,
            weights_mode=options.weights_mode,
        )
        artifact = build_intent_artifact(
            snapshot,
            epoch=epoch,
            expiry=expiry,
            settings=optimizer_settings,
            created_at=created_at,
        )
        artifact.intent_hash = compute_intent_hash(artifact)

        status = "created"
        self.store.save_intent(artifact, status=status)

        if options.submit_onchain:
            if self.relay is None:
                raise RuntimeError(
                    "Onchain submission requested but relay settings are not configured."
                )
            self.relay.publish(artifact)
            status = "submitted"
            self.store.save_intent(artifact, status=status)

        return {
            "status": status,
            "artifact": artifact.to_dict(),
        }

    def get_latest_intent(self) -> dict[str, Any] | None:
        return self.store.get_latest_intent()

    def get_intent(self, epoch: int) -> dict[str, Any] | None:
        return self.store.get_intent(epoch)

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "dbPath": str(self.offchain_settings.db_path),
            "relayEnabled": self.offchain_settings.relay_enabled,
            "defaultStrategy": self.offchain_settings.default_strategy,
        }
