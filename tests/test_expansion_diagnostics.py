from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.expansion_diagnostics import (  # noqa: E402
    filter_out_theme,
    monetary_concentration_rows,
    quarter_key,
    quarterly_drag_rows,
)


class ExpansionDiagnosticsTests(unittest.TestCase):
    def test_filter_out_theme_removes_matching_entries(self) -> None:
        entries = [
            {"event_id": "a", "structural_theme": "monetary_policy"},
            {"event_id": "b", "structural_theme": "geopolitical"},
        ]
        filtered = filter_out_theme(entries, "monetary_policy")
        self.assertEqual([row["event_id"] for row in filtered], ["b"])

    def test_quarter_key_formats_calendar_quarters(self) -> None:
        self.assertEqual(quarter_key("2022-01-03"), "2022Q1")
        self.assertEqual(quarter_key("2022-11-15"), "2022Q4")

    def test_monetary_concentration_ranks_by_cumulative_hazard(self) -> None:
        rows = [
            {"event_id": "fed_a", "date": "2023-01-02", "question": "A", "structural_theme": "monetary_policy", "hazard_contribution": 2.0},
            {"event_id": "fed_a", "date": "2023-01-03", "question": "A", "structural_theme": "monetary_policy", "hazard_contribution": 1.0},
            {"event_id": "fed_b", "date": "2023-01-02", "question": "B", "structural_theme": "monetary_policy", "hazard_contribution": 1.5},
            {"event_id": "other", "date": "2023-01-02", "question": "C", "structural_theme": "geopolitical", "hazard_contribution": 4.0},
        ]
        ranked = monetary_concentration_rows(rows)
        self.assertEqual([row["event_id"] for row in ranked], ["fed_a", "fed_b"])
        self.assertAlmostEqual(ranked[0]["hazard_share_within_theme"], 3.0 / 4.5)
        self.assertAlmostEqual(ranked[0]["hazard_share_total"], 3.0 / 8.5)

    def test_quarterly_drag_rows_flags_missed_recovery(self) -> None:
        dates = ["2022-01-03", "2022-01-04", "2022-04-01"]
        decomposition_rows = [
            {"rsi": 0.50},
            {"rsi": 0.60},
            {"rsi": 0.95},
        ]
        positions = [0.70, 0.75, 0.95]
        price_returns = [0.0, 0.06, 0.02]
        cassandra_returns = [0.0, 0.02, 0.019]
        rows = quarterly_drag_rows(
            dates,
            decomposition_rows,
            positions,
            price_returns,
            cassandra_returns,
            start_quarter="2022Q1",
            end_quarter="2022Q2",
        )
        self.assertEqual(rows[0]["quarter"], "2022Q1")
        self.assertTrue(rows[0]["missed_recovery_flag"])
        self.assertFalse(rows[1]["missed_recovery_flag"])


if __name__ == "__main__":
    unittest.main()
