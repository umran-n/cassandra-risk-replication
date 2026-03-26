from __future__ import annotations

import json
import shutil
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from api import app as api_app
from cassandra_risk.api_service import build_live_signal_artifacts
from cassandra_risk.signal_contract import SignalContract, Source


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _workspace_tempdir() -> Path:
    root = Path(__file__).resolve().parents[1] / ".tmp_tests"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"api_{uuid4().hex}"
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
            "polymarket": {"display_name": "Polymarket", "enabled": True, "priority": 3, "quality_tier": "B", "role": "liquidity_coverage", "auth_mode": "public"},
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


def _source_markets() -> list[SignalContract]:
    return [
        SignalContract(
            contract_id="polymarket::fed-cut-jun-2026",
            source=Source.POLYMARKET,
            provenance_tier="live_ingested",
            question_text="Will the Fed cut rates in June 2026?",
            structural_theme="monetary_policy",
            proxy_family_id=None,
            aggregation_policy="max",
            probability_raw=0.34,
            probability_calibrated=0.34,
            efficiency_gap_applied=0.0,
            created_at="2026-03-01",
            resolves_at="2026-06-18",
            resolved_outcome=None,
            volume_usd=2100000.0,
            quality_score=0.92,
            is_binary=True,
            is_macro_relevant=True,
            last_updated="2026-03-26T00:00:00Z",
            snapshot_timestamp="2026-03-26T00:00:00Z",
            category="Monetary",
            native_id="fed-cut-jun-2026",
            url="https://example.com/fed-cut-jun-2026",
            status="open",
            liquidity_usd=900000.0,
            num_traders=1400,
            raw_category="economy",
            source_priority=3,
            link_key="fed june 2026 cut rates",
            metadata={"history_points": 10},
        ),
        SignalContract(
            contract_id="polymarket::us-recession-2026",
            source=Source.POLYMARKET,
            provenance_tier="live_ingested",
            question_text="Will the US enter recession by December 2026?",
            structural_theme="monetary_policy",
            proxy_family_id=None,
            aggregation_policy="max",
            probability_raw=0.41,
            probability_calibrated=0.41,
            efficiency_gap_applied=0.0,
            created_at="2026-03-01",
            resolves_at="2026-12-31",
            resolved_outcome=None,
            volume_usd=890000.0,
            quality_score=0.62,
            is_binary=True,
            is_macro_relevant=True,
            last_updated="2026-03-26T00:00:00Z",
            snapshot_timestamp="2026-03-26T00:00:00Z",
            category="Monetary",
            native_id="us-recession-2026",
            url="https://example.com/us-recession-2026",
            status="open",
            liquidity_usd=300000.0,
            num_traders=900,
            raw_category="economy",
            source_priority=3,
            link_key="us recession 2026",
            metadata={"history_points": 10},
        ),
    ]


class TestAPIContract(unittest.TestCase):
    def setUp(self) -> None:
        self.root = _workspace_tempdir()
        _write_json(self.root / "config" / "backtest_config.json", _minimal_backtest_config())
        _write_json(self.root / "config" / "source_registry.json", _minimal_source_registry())
        markets = _source_markets()
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
            "market_count": len(markets),
            "fetched_at": "2026-03-26T00:00:00+00:00",
        }

        self.collect_patcher = patch(
            "cassandra_risk.api_service.collect_source_catalogs",
            return_value=(_minimal_source_registry(), markets, [status]),
        )
        self.collect_patcher.start()

        self.original_root = api_app.ROOT
        self.original_output_dir = api_app.OUTPUT_DIR
        api_app.ROOT = self.root
        api_app.OUTPUT_DIR = api_app.signal_output_dir(self.root)
        build_live_signal_artifacts(self.root, refresh=False)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), api_app.SignalAPIHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        api_app.ROOT = self.original_root
        api_app.OUTPUT_DIR = self.original_output_dir
        self.collect_patcher.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def _get_json(self, path: str) -> tuple[int, dict | list]:
        with urllib.request.urlopen(f"{self.base_url}{path}") as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def _post_json(self, path: str, payload: dict | list) -> tuple[int, dict | list]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def _first_candidate_id(self) -> str:
        _status, payload = self._get_json("/v1/admin/promotion/queue")
        return payload[0]["contract_id"]

    def test_registry_endpoint_returns_signal_contracts(self) -> None:
        candidate_id = self._first_candidate_id()
        self._post_json(
            "/v1/admin/promotion/decide",
            {
                "contract_id": candidate_id,
                "decision": "APPROVED",
                "reason": "boundary test approval",
                "proxy_family_id": "test_family",
                "aggregation_policy": "max",
            },
        )
        status, data = self._get_json("/v1/meta/registry")
        self.assertEqual(status, 200)
        required_fields = {
            "contract_id",
            "source",
            "provenance_tier",
            "structural_theme",
            "probability_raw",
            "probability_calibrated",
            "efficiency_gap_applied",
            "resolves_at",
            "volume_usd",
            "quality_score",
            "is_binary",
            "is_macro_relevant",
        }
        for contract in data["contracts"]:
            for field in required_fields:
                self.assertIn(field, contract)

    def test_promotion_decide_writes_to_registry(self) -> None:
        candidate_id = self._first_candidate_id()
        self._post_json(
            "/v1/admin/promotion/decide",
            {
                "contract_id": candidate_id,
                "decision": "APPROVED",
                "reason": "boundary test approval",
                "proxy_family_id": "test_family",
                "aggregation_policy": "max",
            },
        )
        _status, data = self._get_json("/v1/meta/registry")
        ids = [contract["contract_id"] for contract in data["contracts"]]
        self.assertIn(candidate_id, ids)

    def test_promotion_changes_rsi_from_unity(self) -> None:
        _status, before = self._get_json("/v1/rsi/latest")
        self.assertEqual(before["rsi"], 1.0)
        self._post_json(
            "/v1/admin/promotion/decide",
            {
                "contract_id": self._first_candidate_id(),
                "decision": "APPROVED",
                "reason": "boundary test approval",
                "proxy_family_id": "test_family",
                "aggregation_policy": "max",
            },
        )
        _status, after = self._get_json("/v1/rsi/latest")
        self.assertLess(after["rsi"], 1.0)

    def test_audit_trail_records_every_decision(self) -> None:
        _status, before = self._get_json("/v1/admin/promotion/audit")
        count_before = len(before)
        candidate_id = self._first_candidate_id()
        self._post_json(
            "/v1/admin/promotion/decide",
            {
                "contract_id": candidate_id,
                "decision": "APPROVED",
                "reason": "approve for audit count",
                "proxy_family_id": "test_family",
                "aggregation_policy": "max",
            },
        )
        self._post_json(
            "/v1/admin/promotion/decide",
            {
                "contract_id": self._first_candidate_id(),
                "decision": "REJECTED",
                "reason": "reject for audit count",
                "proxy_family_id": "test_family",
                "aggregation_policy": "max",
            },
        )
        _status, after = self._get_json("/v1/admin/promotion/audit")
        self.assertEqual(len(after), count_before + 2)

    def test_sources_markets_returns_all_active_sources(self) -> None:
        _status, data = self._get_json("/v1/sources/markets")
        sources = {market["source"] for market in data}
        self.assertIn("polymarket", sources)


if __name__ == "__main__":
    unittest.main()
