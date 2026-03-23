from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.discovery import apply_curated_decisions, build_query_pack, collapse_duplicate_candidates
from cassandra_risk.events import merge_seeds_with_shortlist


class DiscoveryTests(unittest.TestCase):
    def test_build_query_pack_includes_seed_and_systemic_queries(self) -> None:
        config = {"sample": {"start": "2020-01-01", "end": "2025-01-10"}}
        seeds = [
            {
                "event_id": "custom_event",
                "category": "Sovereign",
                "question": "Will a banking crisis hit in 2024?",
                "event_date": "2024-11-15",
                "manifold_search_terms": ["banking crisis 2024"],
            }
        ]
        queries = build_query_pack(config, seeds)
        query_text = {row["query"] for row in queries}
        self.assertIn("banking crisis 2024", query_text)
        self.assertIn("trade war 2025", query_text)

    def test_collapse_duplicate_candidates_merges_same_question(self) -> None:
        candidates = [
            {
                "market_id": "a",
                "question": "Will the 10-year Treasury rate hit 5% by the end of 2023?",
                "question_normalized": "10 2023 end hit rate the treasury will year",
                "created_date": "2023-10-09",
                "matched_terms": {"10 year treasury 5% end of 2023"},
                "query_sources": {"seed"},
                "event_link_score": 5.0,
                "search_rank": 1,
            },
            {
                "market_id": "b",
                "question": "Will the 10-year Treasury rate hit 5% by the end of 2023?",
                "question_normalized": "10 2023 end hit rate the treasury will year",
                "created_date": "2023-10-10",
                "matched_terms": {"higher for longer rates 2024"},
                "query_sources": {"systemic"},
                "event_link_score": 2.0,
                "search_rank": 3,
            },
        ]
        collapsed = collapse_duplicate_candidates(candidates)
        self.assertEqual(len(collapsed), 1)
        self.assertEqual(collapsed[0]["market_id"], "a")
        self.assertIn("b", collapsed[0]["duplicate_market_ids"])

    def test_merge_seeds_with_shortlist_replaces_without_mutating_inputs(self) -> None:
        seeds = [
            {
                "event_id": "oct_selloff_2023",
                "source": "Manual",
                "category": "Monetary",
                "question": "Manual proxy",
            },
            {
                "event_id": "other_event",
                "source": "Manual",
                "category": "Sovereign",
                "question": "Keep me",
            },
        ]
        shortlist = [
            {
                "event_id": "oct_selloff_2023",
                "source": "Manifold",
                "category": "Monetary",
                "question": "Approved market",
                "market_id": "market-1",
                "selection_reason": "approved",
            }
        ]
        merged, audit = merge_seeds_with_shortlist(seeds, shortlist)
        merged_by_event = {row["event_id"]: row for row in merged}
        self.assertEqual(merged_by_event["oct_selloff_2023"]["source"], "Manifold")
        self.assertEqual(seeds[0]["source"], "Manual")
        self.assertEqual(audit[0]["event_id"], "oct_selloff_2023")

    @patch("cassandra_risk.discovery.candidate_history_summary")
    def test_apply_curated_decisions_rejects_post_event_market_even_if_shortlisted(self, mock_history) -> None:
        mock_history.return_value = (True, 12)
        candidates = [
            {
                "market_id": "market-2",
                "question": "Will another top 20 bank fail before June 1, 2023?",
                "question_normalized": "2023 20 another bank before fail june top will",
                "url_slug": "",
                "created_date": "2023-03-11",
                "close_date": None,
                "resolution_date": "2023-05-01",
                "resolved_outcome": "YES",
                "query": "Silicon Valley Bank another bank fail March 2023",
                "category_guess": "Sovereign",
                "analysis_bucket_guess": "drawdown",
                "event_id_guess": "svb_contagion_2023",
                "event_link_score": 6.0,
                "category_score": 3.0,
                "search_rank": 1,
                "matched_terms": {"Silicon Valley Bank another bank fail March 2023"},
                "query_sources": {"seed"},
                "binary_market": True,
                "liquidity": 0.0,
                "volume": 0.0,
                "duplicate_market_ids": [],
            }
        ]
        seeds = [
            {
                "event_id": "svb_contagion_2023",
                "category": "Sovereign",
                "question": "Will a major US bank failure trigger a March 2023 equity drawdown?",
                "event_date": "2023-03-10",
                "analysis_bucket": "drawdown",
                "manifold_search_terms": ["Silicon Valley Bank another bank fail March 2023"],
            }
        ]
        shortlist = [
            {
                "market_id": "market-2",
                "event_id": "svb_contagion_2023",
                "selection_reason": "approved",
            }
        ]
        rows = apply_curated_decisions(candidates, seeds, shortlist, [], ROOT, refresh=False)
        self.assertEqual(rows[0]["status"], "rejected")
        self.assertEqual(rows[0]["reject_reason"], "created_after_event_window")


if __name__ == "__main__":
    unittest.main()
