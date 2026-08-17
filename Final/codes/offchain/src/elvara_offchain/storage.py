from __future__ import annotations

from pathlib import Path
import json
import sqlite3
from typing import Any

from .models import IntentArtifact


class IntentStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS intents (
                    epoch INTEGER PRIMARY KEY,
                    strategy TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expiry INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    metadata_hash TEXT NOT NULL,
                    intent_hash TEXT,
                    tx_hash TEXT,
                    artifact_json TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def next_epoch(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COALESCE(MAX(epoch), 0) AS latest FROM intents").fetchone()
        return int(row["latest"]) + 1

    def save_intent(self, artifact: IntentArtifact, *, status: str) -> None:
        payload = json.dumps(artifact.to_dict(), sort_keys=True)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO intents (
                    epoch,
                    strategy,
                    as_of,
                    created_at,
                    expiry,
                    status,
                    metadata_hash,
                    intent_hash,
                    tx_hash,
                    artifact_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(epoch) DO UPDATE SET
                    strategy = excluded.strategy,
                    as_of = excluded.as_of,
                    created_at = excluded.created_at,
                    expiry = excluded.expiry,
                    status = excluded.status,
                    metadata_hash = excluded.metadata_hash,
                    intent_hash = excluded.intent_hash,
                    tx_hash = excluded.tx_hash,
                    artifact_json = excluded.artifact_json
                """,
                (
                    artifact.epoch,
                    artifact.strategy,
                    artifact.as_of,
                    artifact.created_at,
                    artifact.expiry,
                    status,
                    artifact.metadata_hash,
                    artifact.intent_hash,
                    artifact.tx_hash,
                    payload,
                ),
            )
            connection.commit()

    def get_intent(self, epoch: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM intents WHERE epoch = ?",
                (epoch,),
            ).fetchone()
        return self._row_to_payload(row)

    def get_latest_intent(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM intents ORDER BY epoch DESC LIMIT 1"
            ).fetchone()
        return self._row_to_payload(row)

    @staticmethod
    def _row_to_payload(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        artifact = json.loads(row["artifact_json"])
        return {
            "epoch": row["epoch"],
            "status": row["status"],
            "metadataHash": row["metadata_hash"],
            "intentHash": row["intent_hash"],
            "txHash": row["tx_hash"],
            "artifact": artifact,
        }
