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


if __name__ == "__main__":
    unittest.main()
