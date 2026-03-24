from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.polymarket import (  # noqa: E402
    choose_probability_token,
    compress_history_daily,
    informative_probability_stats,
    infer_theme_and_category,
)


class PolymarketTests(unittest.TestCase):
    def test_infer_theme_and_category_maps_fed_market_to_monetary(self) -> None:
        theme, category, _, confidence = infer_theme_and_category(
            "Business",
            "Will the Fed cut rates by September 2024?",
            "Fed cuts in 2024",
        )
        self.assertEqual(theme, "monetary_policy")
        self.assertEqual(category, "Monetary")
        self.assertGreater(confidence, 0.0)

    def test_infer_theme_and_category_rejects_noise(self) -> None:
        theme, category, raw_label, confidence = infer_theme_and_category(
            "None",
            "Total Kills Over/Under 53.5 in Game 1?",
            "Esports lines",
        )
        self.assertEqual(theme, "noise")
        self.assertEqual(category, "Noise")
        self.assertEqual(raw_label, "none")
        self.assertEqual(confidence, 0.0)

    def test_choose_probability_token_prefers_yes_label(self) -> None:
        token_id, label, outcomes, token_ids = choose_probability_token(
            {
                "outcomes": '["Yes", "No"]',
                "clobTokenIds": '["yes-token", "no-token"]',
            }
        )
        self.assertEqual(token_id, "yes-token")
        self.assertEqual(label, "Yes")
        self.assertEqual(outcomes, ["Yes", "No"])
        self.assertEqual(token_ids, ["yes-token", "no-token"])

    def test_compress_history_daily_keeps_last_point_per_day(self) -> None:
        compressed = compress_history_daily(
            [
                {"t": 1722470400, "p": 0.20},
                {"t": 1722474000, "p": 0.35},
                {"t": 1722556800, "p": 0.55},
            ]
        )
        self.assertEqual(compressed, [
            {"date": "2024-08-01", "probability": 0.35},
            {"date": "2024-08-02", "probability": 0.55},
        ])

    def test_informative_probability_stats_uses_in_band_points(self) -> None:
        passed, count, min_value, max_value = informative_probability_stats(
            [
                {"date": "2024-08-01", "probability": 0.03},
                {"date": "2024-08-02", "probability": 0.27},
                {"date": "2024-08-03", "probability": 0.91},
            ]
        )
        self.assertTrue(passed)
        self.assertEqual(count, 1)
        self.assertAlmostEqual(min_value, 0.03)
        self.assertAlmostEqual(max_value, 0.91)


if __name__ == "__main__":
    unittest.main()
