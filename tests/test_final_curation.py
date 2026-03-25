from __future__ import annotations

import unittest

from cassandra_risk.final_curation import (
    MANUAL_METACULUS_EVENTS,
    apply_israel_arc_cap,
    build_final_universe,
)


class FinalCurationTests(unittest.TestCase):
    def test_apply_israel_arc_cap_keeps_only_named_anchor_rows(self) -> None:
        rows = [
            {"title": "Israel x Hezbollah Ceasefire in 2024?", "theme": "geopolitical", "resolution_date": "2024-12-05", "peak_probability": "0.9", "total_volume_usd": "1"},
            {"title": "Will Israel invade Lebanon before November?", "theme": "geopolitical", "resolution_date": "2024-10-06", "peak_probability": "0.9", "total_volume_usd": "1"},
            {"title": "Will Ukraine sever the land bridge between Crimea and Russia before Nov 1?", "theme": "geopolitical", "resolution_date": "2023-11-01", "peak_probability": "0.3", "total_volume_usd": "1"},
        ]
        kept, dropped = apply_israel_arc_cap(rows)
        self.assertEqual(
            {row["title"] for row in kept},
            {"Israel x Hezbollah Ceasefire in 2024?", "Will Ukraine sever the land bridge between Crimea and Russia before Nov 1?"},
        )
        self.assertEqual([row["title"] for row in dropped], ["Will Israel invade Lebanon before November?"])

    def test_build_final_universe_appends_manual_metaculus_events(self) -> None:
        rows = [
            {"title": "US debt ceiling hike by July 1?", "theme": "fiscal_debt", "resolution_date": "2023-06-03", "peak_probability": "0.995", "total_volume_usd": "108835.7"},
        ]
        approved, dropped = build_final_universe(rows)
        self.assertEqual(len(dropped), 0)
        self.assertEqual(len(approved), 1 + len(MANUAL_METACULUS_EVENTS))
        self.assertEqual(sum(1 for row in approved if row["source"] == "metaculus"), len(MANUAL_METACULUS_EVENTS))


if __name__ == "__main__":
    unittest.main()
