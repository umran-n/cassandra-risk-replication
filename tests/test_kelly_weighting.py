from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.backtest import hazard_components_for_row
from cassandra_risk.kelly_weighting import (
    apply_kelly_weighting,
    becker_corrected_probability,
    kelly_fraction,
    scaled_kelly_fraction,
    kelly_weighted_probability,
)


class KellyWeightingTests(unittest.TestCase):
    def test_becker_corrected_probability_uses_clip_raw_minus_gap(self) -> None:
        self.assertAlmostEqual(becker_corrected_probability(0.60, 0.0732), 0.5268, places=6)
        self.assertEqual(becker_corrected_probability(0.02, 0.0732), 0.0)

    def test_kelly_fraction_matches_prespec(self) -> None:
        self.assertAlmostEqual(kelly_fraction(0.5268), 0.0536, places=6)
        self.assertAlmostEqual(kelly_weighted_probability(0.5268), 0.02823648, places=8)
        self.assertAlmostEqual(scaled_kelly_fraction(0.5268, 0.50), 0.0268, places=6)
        self.assertAlmostEqual(kelly_weighted_probability(0.5268, 0.50), 0.01411824, places=8)
        self.assertAlmostEqual(kelly_weighted_probability(0.5268, 0.25), 0.00705912, places=8)

    def test_apply_kelly_weighting_uses_becker_original_probability_when_available(self) -> None:
        config = {"becker_calibration": {"enabled": True}}
        daily_events = {
            "2024-01-02": {
                "event-1": {
                    "event_id": "event-1",
                    "category": "Kinetic",
                    "probability": 0.55,
                    "becker_original_probability": 0.60,
                    "resolution_date": "2024-01-17",
                    "structural_theme": "geopolitical",
                    "question": "Test question",
                }
            }
        }
        weighted = apply_kelly_weighting(daily_events, config)
        row = weighted["2024-01-02"]["event-1"]
        self.assertEqual(row["kelly_weighting"], "enabled")
        self.assertAlmostEqual(row["kelly_fraction_scale"], 1.0, places=6)
        self.assertAlmostEqual(row["kelly_efficiency_gap"], 0.0732, places=6)
        self.assertAlmostEqual(row["kelly_becker_probability"], 0.5268, places=6)
        self.assertAlmostEqual(row["kelly_fraction"], 0.0536, places=6)
        self.assertAlmostEqual(row["probability"], 0.02823648, places=8)

    def test_apply_kelly_weighting_supports_fractional_scale(self) -> None:
        config = {"becker_calibration": {"enabled": True}}
        daily_events = {
            "2024-01-02": {
                "event-1": {
                    "event_id": "event-1",
                    "category": "Kinetic",
                    "probability": 0.60,
                    "resolution_date": "2024-01-17",
                    "structural_theme": "geopolitical",
                    "question": "Test question",
                }
            }
        }
        weighted = apply_kelly_weighting(daily_events, config, fraction_scale=0.50)
        row = weighted["2024-01-02"]["event-1"]
        self.assertAlmostEqual(row["kelly_fraction_scale"], 0.50, places=6)
        self.assertAlmostEqual(row["kelly_fraction"], 0.0268, places=6)
        self.assertAlmostEqual(row["probability"], 0.01411824, places=8)

    def test_hazard_components_allow_signed_probability_for_kelly_rows(self) -> None:
        config = {
            "cassandra": {
                "category_weights": {"Kinetic": 10.0},
                "category_lambdas": {"Kinetic": 0.1},
                "horizon_normalizer_days": 30,
            }
        }
        row = {
            "category": "Kinetic",
            "probability": -0.1,
            "resolution_date": "2024-01-17",
            "kelly_weighting": "enabled",
        }
        components = hazard_components_for_row(row, "2024-01-02", config)
        self.assertLess(components["probability_factor"], 0.0)
        self.assertLess(components["hazard_contribution"], 0.0)


if __name__ == "__main__":
    unittest.main()
