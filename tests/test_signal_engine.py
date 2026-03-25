from __future__ import annotations

from pathlib import Path
import unittest

from cassandra_risk.signal_engine import build_signal_book
from cassandra_risk.source_registry import load_source_registry


ROOT = Path(__file__).resolve().parents[1]


class SignalEngineTests(unittest.TestCase):
    def test_build_signal_book_keeps_discovered_candidates_out_of_governed_snapshots(self) -> None:
        registry = load_source_registry(ROOT)
        families = [
            {
                "event_family_id": "rate_hike_shock_2022",
                "title": "Aggressive Fed tightening risk",
                "structural_theme": "monetary_policy",
                "category": "Monetary",
                "governance_source": "seed_file",
                "proxy_family_id": "rate_hike_shock_2022",
                "source_candidates": [],
                "discovered": False,
                "linked_markets": [
                    {
                        "source": "polymarket",
                        "market_id": "pm1",
                        "title": "Aggressive Fed tightening risk",
                        "status": "open",
                        "current_probability": 0.9,
                        "quality_score": 0.8,
                        "structural_theme": "monetary_policy",
                        "category": "Monetary",
                        "close_time": "2026-06-30",
                    }
                ],
            },
            {
                "event_family_id": "discovered_polymarket_1",
                "title": "US strikes on Iran in 2026?",
                "structural_theme": "geopolitical",
                "category": "Kinetic",
                "governance_source": "autonomous_discovery",
                "proxy_family_id": "discovered_geopolitical_polymarket",
                "source_candidates": [],
                "discovered": True,
                "linked_markets": [
                    {
                        "source": "polymarket",
                        "market_id": "pm2",
                        "title": "US strikes on Iran in 2026?",
                        "status": "open",
                        "current_probability": 0.4,
                        "quality_score": 0.9,
                        "structural_theme": "geopolitical",
                        "category": "Kinetic",
                        "close_time": "2026-09-30",
                    }
                ],
            },
        ]
        family_rows, snapshots, rsi_snapshot = build_signal_book(families, registry, ROOT)
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["event_family_id"], "rate_hike_shock_2022")
        self.assertEqual(snapshots[0]["calibration_applied"], "becker")
        discovered_row = next(row for row in family_rows if row["event_family_id"] == "discovered_polymarket_1")
        self.assertEqual(discovered_row["selection_state"], "candidate_only")
        self.assertEqual(rsi_snapshot["event_count"], 1)


if __name__ == "__main__":
    unittest.main()
