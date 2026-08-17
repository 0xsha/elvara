from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[1]

    def test_today_cannot_be_combined_with_sample(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "elvara_offchain.cli",
                "generate-intent",
                "--strategy",
                "CVaR",
                "--sample",
                "--today",
            ],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot be combined", result.stderr)

    def test_output_writes_canonical_artifact_only(self) -> None:
        expected = json.loads(
            (self.project_root / "examples" / "sample-intent.json").read_text(
                encoding="utf-8"
            )
        )

        with tempfile.TemporaryDirectory() as tempdir:
            output_path = Path(tempdir) / "sample-intent.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "elvara_offchain.cli",
                    "generate-intent",
                    "--strategy",
                    "CVaR",
                    "--sample",
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )
            actual = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(actual, expected)
        self.assertNotIn("artifact", actual)


if __name__ == "__main__":
    unittest.main()
