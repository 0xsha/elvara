from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
import os

from dotenv import load_dotenv


DEFAULT_TICKERS: dict[str, str] = {
    "Gold": "GLD",
    "Silver": "SLV",
    "Oil": "USO",
    "REIT": "VNQ",
    "Treasury": "TLT",
    "EnergyInfra": "AMLP",
    "Agri": "DBA",
}

# Canonical mock asset addresses for the single-chain PoC.
DEFAULT_ASSET_ADDRESSES: dict[str, str] = {
    "Gold": "0x0000000000000000000000000000000000000001",
    "Silver": "0x0000000000000000000000000000000000000002",
    "Oil": "0x0000000000000000000000000000000000000003",
    "REIT": "0x0000000000000000000000000000000000000004",
    "Treasury": "0x0000000000000000000000000000000000000005",
    "EnergyInfra": "0x0000000000000000000000000000000000000006",
    "Agri": "0x0000000000000000000000000000000000000007",
}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
EXAMPLES_DIR = PROJECT_ROOT / "examples"


@dataclass(frozen=True, slots=True)
class OptimizerSettings:
    start_date: str = "2021-03-01"
    end_date: str = "2026-03-03"
    min_train_days: int = 504
    test_days: int = 63
    step_days: int = 63
    transaction_cost_bps: int = 10
    trading_days: int = 252
    initial_value: int = 1_000_000
    base_min_weight: float = 0.05
    base_max_weight: float = 0.35
    tickers: Mapping[str, str] = field(default_factory=lambda: dict(DEFAULT_TICKERS))
    asset_addresses: Mapping[str, str] = field(
        default_factory=lambda: dict(DEFAULT_ASSET_ADDRESSES)
    )

    @property
    def cost_rate(self) -> float:
        return self.transaction_cost_bps / 10_000


@dataclass(frozen=True, slots=True)
class OffchainSettings:
    rpc_url: str | None = None
    private_key: str | None = None
    contract_address: str | None = None
    default_strategy: str = "CVaR"
    default_expiry_seconds: int = 3600
    db_path: Path = DATA_DIR / "intents.db"

    @property
    def relay_enabled(self) -> bool:
        return bool(self.rpc_url and self.private_key and self.contract_address)


def load_offchain_settings(env_file: str | Path | None = None) -> OffchainSettings:
    default_env = PROJECT_ROOT / ".env"
    load_dotenv(env_file or default_env, override=False)

    db_path = Path(os.getenv("ELVARA_DB_PATH", str(DATA_DIR / "intents.db")))
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
    return OffchainSettings(
        rpc_url=os.getenv("ELVARA_RPC_URL"),
        private_key=os.getenv("ELVARA_PRIVATE_KEY"),
        contract_address=os.getenv("ELVARA_CONTRACT_ADDRESS"),
        default_strategy=os.getenv("ELVARA_DEFAULT_STRATEGY", "CVaR"),
        default_expiry_seconds=int(os.getenv("ELVARA_DEFAULT_EXPIRY_SECONDS", "3600")),
        db_path=db_path,
    )
