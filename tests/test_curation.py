from __future__ import annotations

import unittest

from cassandra_risk.curation import build_curator_markdown, build_curator_rows, suggested_action


class CurationTests(unittest.TestCase):
    def test_suggested_action_flags_electoral_and_low_liquidity(self) -> None:
        candidate = {"structural_theme": "electoral", "volume": 5000}
        self.assertEqual(suggested_action(candidate), "REVIEW_CAP|LOW_LIQUIDITY")

    def test_build_curator_rows_sorts_by_theme_then_volume_desc(self) -> None:
        rows = build_curator_rows(
            [
                {"title": "B", "structural_theme": "monetary_policy", "volume": 1000, "peak_probability": 0.7, "min_probability": 0.2, "history_point_count": 10},
                {"title": "A", "structural_theme": "electoral", "volume": 2000, "peak_probability": 0.8, "min_probability": 0.3, "history_point_count": 5},
                {"title": "C", "structural_theme": "electoral", "volume": 1000, "peak_probability": 0.6, "min_probability": 0.1, "history_point_count": 8},
            ]
        )
        self.assertEqual([row["title"] for row in rows], ["A", "C", "B"])

    def test_markdown_groups_by_theme(self) -> None:
        rows = build_curator_rows(
            [
                {"title": "Rate cut", "structural_theme": "monetary_policy", "volume": 20000, "peak_probability": 0.8, "min_probability": 0.2, "history_point_count": 12},
            ]
        )
        content = build_curator_markdown(rows)
        self.assertIn("## monetary_policy", content)
        self.assertIn("Rate cut", content)


if __name__ == "__main__":
    unittest.main()
