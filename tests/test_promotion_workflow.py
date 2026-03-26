from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from cassandra_risk.api_service import build_live_signal_artifacts
from cassandra_risk.promotion_store import apply_promotion_decision, latest_decisions_map, load_signal_registry
from cassandra_risk.promotion_workflow import PromotionCandidate, build_promotion_queue
from cassandra_risk.signal_contract import SignalContract


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _workspace_tempdir() -> Path:
    root = Path(__file__).resolve().parents[1] / ".tmp_tests"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"promotion_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    def test_load_signal_registry_backfills_missing_aggregation_policy(self) -> None:
        root = _workspace_tempdir()
        try:
            _write_json(
                root / "data" / "governed" / "signal_registry.json",
                [
                    {
                        "event_family_id": "iran_family",
                        "title": "Another Israeli military action against Iran in 2026?",
                        "structural_theme": "geopolitical",
                        "theme": "geopolitical",
                        "category": "Kinetic",
                        "governance_source": "signal_registry_bootstrap",
                        "proxy_family_id": "iran_family",
                        "source_candidates": [
                            {
                                "link_type": "governed_reference",
                                "source": "polymarket",
                                "market_id": "pm_iran",
                                "title": "Another Israeli military action against Iran in 2026?",
                                "resolution_date": "2026-06-30",
                            }
                        ],
                        "discovered": False,
                        "notes": "legacy row without policy",
                    }
                ],
            )
            rows = load_signal_registry(root, bootstrap=False)
            self.assertEqual("weighted_average", rows[0]["aggregation_policy"])
            self.assertTrue(rows[0]["_policy_backfilled"])
            self.assertEqual("weighted_average", rows[0]["source_candidates"][0]["aggregation_policy"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_build_promotion_queue_scores_clean_live_candidate_as_auto_approve(self) -> None:
        root = _workspace_tempdir()
        try:
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
                        "contract_id": "polymarket::123",
                        "source": "polymarket",
                        "native_id": "123",
                        "market_id": "123",
                        "provenance_tier": "live_ingested",
                        "aggregation_policy": "max",
                        "question_text": "Will the Fed cut rates in June 2026?",
                        "title": "Will the Fed cut rates in June 2026?",
                        "structural_theme": "monetary_policy",
                        "category": "Monetary",
                        "probability_raw": 0.34,
                        "probability_calibrated": 0.34,
                        "efficiency_gap_applied": 0.0,
                        "current_probability": 0.34,
                        "volume_usd": 2_100_000,
                        "liquidity_usd": 600_000,
                        "num_traders": 1500,
                        "created_at": "2026-03-01",
                        "open_time": "2026-03-01",
                        "resolves_at": "2026-06-18",
                        "close_time": "2026-06-18",
                        "resolution_time": "2026-06-18",
                        "is_binary": True,
                        "outcome_type": "BINARY",
                        "quality_score": 0.92,
                        "is_macro_relevant": True,
                        "last_updated": "2026-03-26T00:00:00Z",
                        "snapshot_timestamp": "2026-03-26T00:00:00Z",
                        "url": "https://example.com/m1",
                        "metadata": {},
                    }
                ],
            )

            queue = build_promotion_queue(root)
            self.assertEqual(1, len(queue))
            self.assertIsInstance(queue[0], PromotionCandidate)
            self.assertIsInstance(queue[0].contract, SignalContract)
            self.assertEqual("APPROVE", queue[0].auto_recommendation)
            self.assertEqual(7, queue[0].gates_passed)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_promotion_decision_turns_discovered_candidate_into_governed_signal(self) -> None:
        root = _workspace_tempdir()
        try:
            _write_json(root / "config" / "backtest_config.json", _minimal_backtest_config())
            _write_json(root / "config" / "source_registry.json", _minimal_source_registry())

            market = {
                "contract_id": "polymarket::fed-cut-jun-2026",
                "source": "polymarket",
                "native_id": "fed-cut-jun-2026",
                "market_id": "fed-cut-jun-2026",
                "provenance_tier": "live_ingested",
                "aggregation_policy": "max",
                "question_text": "Will the Fed cut rates in June 2026?",
                "title": "Will the Fed cut rates in June 2026?",
                "url": "https://example.com/fed-cut-jun-2026",
                "status": "open",
                "outcome_type": "BINARY",
                "structural_theme": "monetary_policy",
                "category": "Monetary",
                "probability_raw": 0.34,
                "probability_calibrated": 0.34,
                "efficiency_gap_applied": 0.0,
                "current_probability": 0.34,
                "volume_usd": 2_100_000.0,
                "liquidity_usd": 900_000.0,
                "num_traders": 1400,
                "created_at": "2026-03-01",
                "open_time": "2026-03-01",
                "resolves_at": "2026-06-18",
                "close_time": "2026-06-18",
                "resolution_time": "2026-06-18",
                "raw_category": "economy",
                "quality_score": 0.92,
                "is_binary": True,
                "is_macro_relevant": True,
                "last_updated": "2026-03-26T00:00:00Z",
                "snapshot_timestamp": "2026-03-26T00:00:00Z",
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
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_promotion_candidate_contains_signal_contract(self) -> None:
        root = _workspace_tempdir()
        try:
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
                        "contract_id": "polymarket::123",
                        "source": "polymarket",
                        "native_id": "123",
                        "question_text": "Will the Fed cut rates in June 2026?",
                        "structural_theme": "monetary_policy",
                        "category": "Monetary",
                        "provenance_tier": "live_ingested",
                        "aggregation_policy": "max",
                        "probability_raw": 0.34,
                        "probability_calibrated": 0.34,
                        "efficiency_gap_applied": 0.0,
                        "created_at": "2026-03-01",
                        "resolves_at": "2026-06-18",
                        "resolved_outcome": None,
                        "volume_usd": 2100000.0,
                        "quality_score": 0.92,
                        "is_binary": True,
                        "is_macro_relevant": True,
                        "last_updated": "2026-03-26T00:00:00Z",
                        "snapshot_timestamp": "2026-03-26T00:00:00Z",
                        "status": "open",
                    }
                ],
            )

            candidate = build_promotion_queue(root)[0]
            self.assertIsInstance(candidate.contract, SignalContract)
            self.assertFalse(hasattr(candidate, "probability_raw"))
            self.assertFalse(hasattr(candidate, "structural_theme"))
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
