from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.geopolitical_subbucket_calibration import (  # noqa: E402
    calibration_metadata_for_title,
    infer_geopolitical_subbucket,
)


class GeopoliticalSubbucketCalibrationTests(unittest.TestCase):
    def test_infer_geopolitical_subbucket_detects_ceasefire(self) -> None:
        self.assertEqual(
            infer_geopolitical_subbucket("Israel x Hamas ceasefire before September?"),
            "ceasefire_deescalation",
        )

    def test_infer_geopolitical_subbucket_detects_intervention(self) -> None:
        self.assertEqual(
            infer_geopolitical_subbucket("U.S. military action against Iran before November?"),
            "great_power_intervention",
        )

    def test_calibration_metadata_for_title_includes_band_and_gap(self) -> None:
        metadata = calibration_metadata_for_title("Will Israel invade Lebanon before November?")
        self.assertEqual(metadata["calibration_subbucket"], "conflict_escalation")
        self.assertAlmostEqual(metadata["subbucket_becker_gap"], 0.0891)
        self.assertEqual(metadata["subbucket_longshot_lower"], 0.10)
        self.assertEqual(metadata["subbucket_longshot_upper"], 0.90)


if __name__ == "__main__":
    unittest.main()
