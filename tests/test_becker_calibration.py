from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.becker_calibration import (  # noqa: E402
    EFFICIENCY_GAPS,
    apply_becker_calibration,
    calibrate_probability,
)


class BeckerCalibrationTests(unittest.TestCase):
    def test_calibrate_probability_shrinks_toward_center(self) -> None:
        probability = 0.60
        calibrated, metadata = calibrate_probability(probability, "geopolitical", {"becker_calibration": {"enabled": True}})
        expected = 0.5 + (probability - 0.5) * (1.0 - EFFICIENCY_GAPS["geopolitical"])
        self.assertAlmostEqual(calibrated, expected)
        self.assertFalse(metadata["becker_longshot_compressed"])

    def test_calibrate_probability_applies_longshot_second_pass(self) -> None:
        probability = 0.90
        calibrated, metadata = calibrate_probability(probability, "geopolitical", {"becker_calibration": {"enabled": True}})
        once = 0.5 + (probability - 0.5) * (1.0 - EFFICIENCY_GAPS["geopolitical"])
        twice = 0.5 + (once - 0.5) * (1.0 - EFFICIENCY_GAPS["geopolitical"])
        self.assertAlmostEqual(calibrated, twice)
        self.assertTrue(metadata["becker_longshot_compressed"])

    def test_apply_becker_calibration_updates_daily_event_probability(self) -> None:
        config = {
            "becker_calibration": {
                "enabled": True,
                "longshot_lower": 0.2,
                "longshot_upper": 0.8,
                "efficiency_gaps": EFFICIENCY_GAPS,
            }
        }
        daily_events = {
            "2024-01-02": {
                "event-1": {
                    "event_id": "event-1",
                    "probability": 0.90,
                    "structural_theme": "geopolitical",
                }
            }
        }
        updated = apply_becker_calibration(daily_events, config)
        self.assertLess(updated["2024-01-02"]["event-1"]["probability"], 0.90)
        self.assertEqual(updated["2024-01-02"]["event-1"]["becker_calibration"], "enabled")

    def test_calibrate_probability_supports_theme_specific_longshot_thresholds(self) -> None:
        config = {
            "becker_calibration": {
                "enabled": True,
                "longshot_lower": 0.2,
                "longshot_upper": 0.8,
                "theme_longshot_thresholds": {
                    "geopolitical": [0.15, 0.85],
                },
            }
        }
        calibrated, metadata = calibrate_probability(0.18, "geopolitical", config)
        expected = 0.5 + (0.18 - 0.5) * (1.0 - EFFICIENCY_GAPS["geopolitical"])
        self.assertAlmostEqual(calibrated, expected)
        self.assertFalse(metadata["becker_longshot_compressed"])

    def test_apply_becker_calibration_respects_skip_themes(self) -> None:
        config = {
            "becker_calibration": {
                "enabled": True,
                "skip_themes": ["geopolitical"],
            }
        }
        daily_events = {
            "2024-01-02": {
                "event-1": {
                    "event_id": "event-1",
                    "probability": 0.90,
                    "structural_theme": "geopolitical",
                }
            }
        }
        updated = apply_becker_calibration(daily_events, config)
        self.assertAlmostEqual(updated["2024-01-02"]["event-1"]["probability"], 0.90)
        self.assertEqual(updated["2024-01-02"]["event-1"]["becker_calibration"], "skipped")

    def test_apply_becker_calibration_uses_subbucket_gap(self) -> None:
        config = {
            "becker_calibration": {
                "enabled": True,
                "subbucket_efficiency_gaps": {
                    "great_power_intervention": 0.0958,
                },
                "subbucket_longshot_thresholds": {
                    "great_power_intervention": [0.05, 0.95],
                },
            }
        }
        daily_events = {
            "2024-01-02": {
                "event-1": {
                    "event_id": "event-1",
                    "probability": 0.90,
                    "structural_theme": "geopolitical",
                    "calibration_subbucket": "great_power_intervention",
                }
            }
        }
        updated = apply_becker_calibration(daily_events, config)
        expected = 0.5 + (0.90 - 0.5) * (1.0 - 0.0958)
        self.assertAlmostEqual(updated["2024-01-02"]["event-1"]["probability"], expected)
        self.assertEqual(updated["2024-01-02"]["event-1"]["becker_calibration_scope"], "subbucket")
        self.assertEqual(updated["2024-01-02"]["event-1"]["becker_calibration_key"], "great_power_intervention")


if __name__ == "__main__":
    unittest.main()
