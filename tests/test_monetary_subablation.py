from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.backtest import hazard_components_for_row  # noqa: E402
from cassandra_risk.monetary_subablation import (  # noqa: E402
    apply_theme_hazard_cap,
    compress_monetary_by_phase,
    monetary_phase_for_resolution_date,
)


class MonetarySubablationTests(unittest.TestCase):
    def test_monetary_phase_for_resolution_date_maps_expected_ranges(self) -> None:
        self.assertEqual(monetary_phase_for_resolution_date("2023-03-22"), "hiking")
        self.assertEqual(monetary_phase_for_resolution_date("2023-12-13"), "pivot")
        self.assertEqual(monetary_phase_for_resolution_date("2024-06-13"), "cutting")
        self.assertIsNone(monetary_phase_for_resolution_date("2025-01-01"))

    def test_compress_monetary_by_phase_keeps_highest_volume_event_per_phase(self) -> None:
        approved_entries = [
            {"event_id": "hike_low", "theme": "monetary_policy", "source": "polymarket", "resolution_date": "2023-03-22", "total_volume_usd": 100.0, "title": "low"},
            {"event_id": "hike_high", "theme": "monetary_policy", "source": "polymarket", "resolution_date": "2023-06-14", "total_volume_usd": 200.0, "title": "high"},
            {"event_id": "pivot", "theme": "monetary_policy", "source": "polymarket", "resolution_date": "2023-12-13", "total_volume_usd": 150.0, "title": "pivot"},
            {"event_id": "cutting", "theme": "monetary_policy", "source": "polymarket", "resolution_date": "2024-06-13", "total_volume_usd": 175.0, "title": "cut"},
            {"event_id": "other", "theme": "geopolitical", "source": "polymarket", "resolution_date": "2024-06-13", "total_volume_usd": 50.0, "title": "other"},
        ]
        approved_seeds = [
            {"event_id": "hike_low", "structural_theme": "monetary_policy"},
            {"event_id": "hike_high", "structural_theme": "monetary_policy"},
            {"event_id": "pivot", "structural_theme": "monetary_policy"},
            {"event_id": "cutting", "structural_theme": "monetary_policy"},
            {"event_id": "other", "structural_theme": "geopolitical"},
        ]

        filtered, selections = compress_monetary_by_phase(approved_entries, approved_seeds)
        self.assertEqual(sorted(row["event_id"] for row in filtered), ["cutting", "hike_high", "other", "pivot"])
        self.assertEqual([row["event_id"] for row in selections], ["hike_high", "pivot", "cutting"])

    def test_apply_theme_hazard_cap_limits_theme_hazard_to_cap_of_original_total(self) -> None:
        config = {
            "cassandra": {
                "category_weights": {"Monetary": 5.0, "Kinetic": 10.0},
                "category_lambdas": {"Monetary": 0.12, "Kinetic": 0.10},
                "horizon_normalizer_days": 30,
                "rebalancing_thresholds": [0.8, 0.5, 0.3],
            }
        }
        daily_events = {
            "2024-01-02": {
                "monetary_a": {
                    "event_id": "monetary_a",
                    "category": "Monetary",
                    "structural_theme": "monetary_policy",
                    "question": "Fed",
                    "probability": 0.8,
                    "resolution_date": "2024-02-01",
                },
                "geo_a": {
                    "event_id": "geo_a",
                    "category": "Kinetic",
                    "structural_theme": "geopolitical",
                    "question": "Geo",
                    "probability": 0.2,
                    "resolution_date": "2024-02-01",
                },
            }
        }

        original_total = sum(
            hazard_components_for_row(row, "2024-01-02", config)["hazard_contribution"]
            for row in daily_events["2024-01-02"].values()
        )
        capped = apply_theme_hazard_cap(daily_events, config, structural_theme="monetary_policy", cap_share=0.30)
        capped_monetary = hazard_components_for_row(capped["2024-01-02"]["monetary_a"], "2024-01-02", config)["hazard_contribution"]
        self.assertLessEqual(capped_monetary, (0.30 * original_total) + 1e-9)
        self.assertLess(capped["2024-01-02"]["monetary_a"]["probability"], 0.8)


if __name__ == "__main__":
    unittest.main()
