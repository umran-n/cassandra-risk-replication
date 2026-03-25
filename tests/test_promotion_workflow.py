from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cassandra_risk.api_service import build_live_signal_artifacts
from cassandra_risk.promotion_store import apply_promotion_decision, latest_decisions_map
from cassandra_risk.promotion_workflow import build_promotion_queue


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _minimal_backtest_config() -> dict:
    return {
        "cassandra": {
            "horizon_normalizer_days": 30,
            "category_weights": {"Kinetic": 10.0, "Sovereign": 8.0, "Trade": 6.0, "Monetary": 5.0, "Technology": 3.0, "None": 0.0},
            "category_lambdas": {"Kinetic": 0.1, "Sovereign": 0.15, "Trade": 0.12, "Monetary": 0.12, "Technology": 0.1, "None": 0.0},
            "source_brier_scores": {"Polymarket": 0.31, "Metaculus": 0.17, "Manifold": 0.21, "Manual": 0.25},
            "rebalancing_thresholds": [0.8, 0.5, 0.3],
        },
        "becker_calibration": {"enabled": False, "efficiency_gaps": {}},
    }


def _minimal_source_registry() -> dict:
    return {
        "sources": {
            "polymarket": {"enabled": True, "priority": 3, "quality_tier": "B", "role": "liquidity_coverage", "auth_mode": "public"},
        },
        "theme_policies": {
            "monetary_policy": {"becker_enabled": True, "becker_gap": 0.0017, "bucket_cap": 0.3, "max_bucket_events": 15, "longshot_threshold": [0.2, 0.8]},
        },
        "selection_policy": {
            "source_priority": ["polymarket"],
            "minimum_text_overlap_score": 0.3,
            "minimum_quality_score": 0.4,
            "max_unlinked_candidates_per_theme": 8,
        },
    }


class PromotionWorkflowTests(unittest.TestCase):
    def test_build_promotion_queue_scores_clean_live_candidate_as_auto_approve(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_json(
                root / "outputs" / "signals" / "family_signal_book.json",
                [
                    {
                        "event_family_id": "discovered_polymarket_123",
                        "title": "Will the Fed cut rates in June 2026?",
                        "structural_theme": "monetary_policy",
                        "category": "Monetary",
                        "discovered": True,
                        "selected_source": "polymarket",
                        "selected_market_id": "123",
                    }
                ],
            )
            _write_json(
                root / "outputs" / "signals" / "source_markets.json",
                [
                    {
                        "source": "polymarket",
                        "market_id": "123",
                        "title": "Will the Fed cut rates in June 2026?",
                        "structural_theme": "monetary_policy",
                        "category": "Monetary",
                        "current_probability": 0.34,
                        "volume_usd": 2_100_000,
                        "liquidity_usd": 600_000,
                        "num_traders": 1500,
                        "open_time": "2026-03-01",
                        "close_time": "2026-06-18",
                        "resolution_time": "2026-06-18",
                        "outcome_type": "BINARY",
                        "quality_score": 0.92,
                        "url": "https://example.com/m1",
                        "metadata": {},
                    }
                ],
            )

            queue = build_promotion_queue(root)
            self.assertEqual(1, len(queue))
            self.assertEqual("APPROVE", queue[0]["auto_recommendation"])
            self.assertEqual(7, queue[0]["gates_passed"])

    def test_promotion_decision_turns_discovered_candidate_into_governed_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_json(root / "config" / "backtest_config.json", _minimal_backtest_config())
            _write_json(root / "config" / "source_registry.json", _minimal_source_registry())

            market = {
                "source": "polymarket",
                "market_id": "fed-cut-jun-2026",
                "title": "Will the Fed cut rates in June 2026?",
                "url": "https://example.com/fed-cut-jun-2026",
                "status": "open",
                "outcome_type": "BINARY",
                "structural_theme": "monetary_policy",
                "category": "Monetary",
                "current_probability": 0.34,
                "volume_usd": 2_100_000.0,
                "liquidity_usd": 900_000.0,
                "num_traders": 1400,
                "open_time": "2026-03-01",
                "close_time": "2026-06-18",
                "resolution_time": "2026-06-18",
                "raw_category": "economy",
                "quality_score": 0.92,
                "source_priority": 3,
                "link_key": "fed june 2026 cut rates",
                "matched_terms": [],
                "metadata": {"history_points": 10},
            }
            status = {
                "source": "polymarket",
                "display_name": "Polymarket",
                "enabled": True,
                "has_credentials": True,
                "reachable": True,
                "auth_mode": "public",
                "quality_tier": "B",
                "role": "liquidity_coverage",
                "notes": "",
                "market_count": 1,
                "fetched_at": "2026-03-26T00:00:00+00:00",
            }

            with patch("cassandra_risk.api_service.collect_source_catalogs", return_value=(_minimal_source_registry(), [market], [status])):
                first = build_live_signal_artifacts(root, refresh=False)
                self.assertEqual(0, len(first["snapshots"]))
                self.assertEqual(1.0, first["rsi_snapshot"]["rsi"])

                queue = build_promotion_queue(root, decisions_map=latest_decisions_map(root))
                self.assertEqual(1, len(queue))
                audit_row = apply_promotion_decision(
                    root,
                    candidate=queue[0],
                    decision="APPROVED",
                    reason="Clean FOMC binary, 84-day horizon.",
                    decided_by="test",
                    proxy_family_id="fed_rate_2026_q2",
                    aggregation_policy="max",
                )
                self.assertEqual("APPROVED", audit_row["decision"])

                second = build_live_signal_artifacts(root, refresh=False)
                self.assertEqual(1, len(second["snapshots"]))
                self.assertLess(second["rsi_snapshot"]["rsi"], 1.0)
                self.assertEqual("fed_rate_2026_q2", second["snapshots"][0]["event_family_id"])


if __name__ == "__main__":
    unittest.main()
