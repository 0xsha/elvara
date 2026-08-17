from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from elvara_offchain.config import OffchainSettings, OptimizerSettings
from elvara_offchain.service import IntentService, RunIntentOptions


class IntentServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(__file__).resolve().parents[1]
        self.db_path = Path(self.tempdir.name) / "intents.db"
        self.service = IntentService(
            optimizer_settings=OptimizerSettings(),
            offchain_settings=OffchainSettings(
                db_path=self.db_path,
                default_strategy="CVaR",
            ),
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_sample_intent_matches_checked_in_artifact(self) -> None:
        expected = json.loads(
            (self.project_root / "examples" / "sample-intent.json").read_text(
                encoding="utf-8"
            )
        )

        first = self.service.run_rebalance(
            RunIntentOptions(strategy="CVaR", use_sample=True)
        )
        second = self.service.run_rebalance(
            RunIntentOptions(strategy="CVaR", use_sample=True)
        )

        self.assertEqual(first["status"], "created")
        self.assertEqual(first["artifact"], expected)
        self.assertEqual(second["artifact"], expected)
        self.assertEqual(sum(first["artifact"]["targetBps"]), 10_000)

    def test_latest_intent_round_trips_from_store(self) -> None:
        created = self.service.run_rebalance(
            RunIntentOptions(strategy="Worst", use_sample=True, epoch=7)
        )
        latest = self.service.get_latest_intent()

        self.assertIsNotNone(latest)
        self.assertEqual(latest["epoch"], 7)
        self.assertEqual(latest["artifact"]["strategy"], "Worst")
        self.assertEqual(
            latest["artifact"]["metadataHash"],
            created["artifact"]["metadataHash"],
        )


if __name__ == "__main__":
    unittest.main()
