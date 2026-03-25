from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in (SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_becker_stack import STACK_CONFIGS, compose_daily_transform  # noqa: E402


class BeckerStackTests(unittest.TestCase):
    def test_stack_configs_match_expected_keys(self) -> None:
        self.assertEqual(
            set(STACK_CONFIGS),
            {"V5_Becker_top5", "V5_Becker_cap30", "V5_Becker_top5_cap"},
        )

    def test_compose_daily_transform_returns_none_when_no_layers_enabled(self) -> None:
        self.assertIsNone(compose_daily_transform(enable_becker=False, bucket_cap=None))

    def test_compose_daily_transform_applies_becker_and_cap(self) -> None:
        config = {
            "becker_calibration": {
                "enabled": True,
                "longshot_lower": 0.2,
                "longshot_upper": 0.8,
                "efficiency_gaps": {
                    "monetary_policy": 0.0017,
                    "geopolitical": 0.0732,
                    "electoral": 0.0102,
                    "trade_technology": 0.0269,
                    "fiscal_debt": 0.0102,
                    "systemic_credit": 0.0102,
                },
            },
            "cassandra": {
                "category_weights": {"Monetary": 5.0, "Kinetic": 10.0},
                "category_lambdas": {"Monetary": 0.12, "Kinetic": 0.10},
                "horizon_normalizer_days": 30,
                "rebalancing_thresholds": [0.8, 0.5, 0.3],
            },
        }
        daily_events = {
            "2024-01-02": {
                "monetary_event": {
                    "event_id": "monetary_event",
                    "probability": 0.90,
                    "structural_theme": "monetary_policy",
                    "category": "Monetary",
                    "question": "Fed",
                    "resolution_date": "2024-02-01",
                },
                "geo_event": {
                    "event_id": "geo_event",
                    "probability": 0.20,
                    "structural_theme": "geopolitical",
                    "category": "Kinetic",
                    "question": "Geo",
                    "resolution_date": "2024-02-01",
                },
            }
        }
        transform = compose_daily_transform(enable_becker=True, bucket_cap=0.30)
        updated = transform(daily_events, config, ["2024-01-02"])
        self.assertIn("becker_calibration", updated["2024-01-02"]["monetary_event"])
        self.assertTrue(updated["2024-01-02"]["monetary_event"]["theme_cap_applied"])


if __name__ == "__main__":
    unittest.main()
