from __future__ import annotations

import unittest

from cassandra_risk.event_graph import build_event_graph


class EventGraphTests(unittest.TestCase):
    def test_build_event_graph_links_explicit_market_id(self) -> None:
        families = [
            {
                "event_family_id": "us_debt_ceiling_2023",
                "title": "US debt ceiling risk",
                "structural_theme": "fiscal_debt",
                "category": "Sovereign",
                "governance_source": "polymarket_approved",
                "proxy_family_id": "pf1",
                "source_candidates": [
                    {"source": "polymarket", "market_id": "123", "title": "US debt ceiling risk"}
                ],
            }
        ]
        markets = [
            {
                "source": "polymarket",
                "market_id": "123",
                "title": "US debt ceiling risk",
                "status": "open",
                "current_probability": 0.55,
                "quality_score": 0.8,
                "structural_theme": "fiscal_debt",
                "category": "Sovereign",
            }
        ]
        registry = {"selection_policy": {"minimum_text_overlap_score": 0.3, "minimum_quality_score": 0.4, "max_unlinked_candidates_per_theme": 8}}
        built, audit = build_event_graph(families, markets, registry)
        self.assertEqual(len(built[0]["linked_markets"]), 1)
        self.assertEqual(built[0]["linked_markets"][0]["link_type"], "explicit_market_id")
        self.assertEqual(audit[0]["event_family_id"], "us_debt_ceiling_2023")

    def test_build_event_graph_promotes_high_quality_unlinked_market_to_discovered_family(self) -> None:
        families = []
        markets = [
            {
                "source": "manifold",
                "market_id": "m1",
                "title": "Will the US invade Iran before the end of 2026?",
                "status": "open",
                "current_probability": 0.42,
                "quality_score": 0.7,
                "structural_theme": "geopolitical",
                "category": "Kinetic",
            }
        ]
        registry = {"selection_policy": {"minimum_text_overlap_score": 0.3, "minimum_quality_score": 0.4, "max_unlinked_candidates_per_theme": 8}}
        built, _audit = build_event_graph(families, markets, registry)
        self.assertEqual(len(built), 1)
        self.assertTrue(built[0]["discovered"])
        self.assertEqual(built[0]["linked_markets"][0]["link_type"], "autonomous_discovery")

    def test_build_event_graph_does_not_similarity_link_far_future_market_to_historical_family(self) -> None:
        families = [
            {
                "event_family_id": "monetary_policy_no_change_in_fed_interest_rates_after_2024_september_meeting_2024",
                "title": "Will there be no change in Fed interest rates after the September 2024 meeting?",
                "structural_theme": "monetary_policy",
                "category": "Monetary",
                "governance_source": "polymarket_approved",
                "proxy_family_id": "pf_monetary",
                "source_candidates": [
                    {"source": "polymarket", "market_id": "old1", "title": "September 2024 Fed hold", "resolution_date": "2024-09-18"}
                ],
            }
        ]
        markets = [
            {
                "source": "polymarket",
                "market_id": "live2026",
                "title": "Will there be no change in Fed interest rates after the April 2026 meeting?",
                "status": "open",
                "current_probability": 0.62,
                "quality_score": 0.9,
                "structural_theme": "monetary_policy",
                "category": "Monetary",
                "resolution_time": "2026-04-01",
            }
        ]
        registry = {"selection_policy": {"minimum_text_overlap_score": 0.3, "minimum_quality_score": 0.4, "max_unlinked_candidates_per_theme": 8}}
        built, audit = build_event_graph(families, markets, registry)
        self.assertEqual("unlinked", audit[0]["link_status"])
        self.assertEqual(2, len(built))
        self.assertTrue(any(row.get("discovered") for row in built))
        self.assertFalse(any(row.get("linked_markets") for row in built if row["event_family_id"] == families[0]["event_family_id"]))


if __name__ == "__main__":
    unittest.main()
