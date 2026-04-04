from __future__ import annotations

import json
import os
import shutil
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
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
        self.original_public_key = os.environ.get("CASSANDRA_API_KEY")
        self.original_operator_key = os.environ.get("CASSANDRA_OPERATOR_KEY")
        self.original_enterprise_key = os.environ.get("CASSANDRA_ENTERPRISE_KEY")
        os.environ["CASSANDRA_API_KEY"] = "public-test-key"
        os.environ["CASSANDRA_OPERATOR_KEY"] = "operator-test-key"
        os.environ["CASSANDRA_ENTERPRISE_KEY"] = "enterprise-test-key"
        api_app.ROOT = self.root
        api_app.OUTPUT_DIR = api_app.signal_output_dir(self.root)
        api_app.SignalAPIHandler._rate_limit_state.clear()
        self.original_public_rate_limits = dict(api_app.SignalAPIHandler.public_rate_limits)
        self.original_rate_limit_window_seconds = api_app.SignalAPIHandler.rate_limit_window_seconds
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
        api_app.SignalAPIHandler.public_rate_limits = self.original_public_rate_limits
        api_app.SignalAPIHandler.rate_limit_window_seconds = self.original_rate_limit_window_seconds
        api_app.SignalAPIHandler._rate_limit_state.clear()
        if self.original_public_key is None:
            os.environ.pop("CASSANDRA_API_KEY", None)
        else:
            os.environ["CASSANDRA_API_KEY"] = self.original_public_key
        if self.original_operator_key is None:
            os.environ.pop("CASSANDRA_OPERATOR_KEY", None)
        else:
            os.environ["CASSANDRA_OPERATOR_KEY"] = self.original_operator_key
        if self.original_enterprise_key is None:
            os.environ.pop("CASSANDRA_ENTERPRISE_KEY", None)
        else:
            os.environ["CASSANDRA_ENTERPRISE_KEY"] = self.original_enterprise_key
        self.collect_patcher.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def _get_json(self, path: str, headers: dict[str, str] | None = None) -> tuple[int, dict | list]:
        request = urllib.request.Request(f"{self.base_url}{path}", headers=headers or {})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def _post_json(self, path: str, payload: dict | list, headers: dict[str, str] | None = None) -> tuple[int, dict | list]:
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def _public_headers(self) -> dict[str, str]:
        return {"X-API-Key": "public-test-key"}

    def _operator_headers(self) -> dict[str, str]:
        return {"X-Operator-Key": "operator-test-key"}

    def _enterprise_headers(self) -> dict[str, str]:
        return {"X-Enterprise-Key": "enterprise-test-key"}

    def _first_candidate_id(self) -> str:
        _status, payload = self._get_json("/v1/admin/promotion/queue", headers=self._operator_headers())
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
            headers=self._operator_headers(),
        )
        status, data = self._get_json("/v1/meta/registry", headers=self._operator_headers())
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
            headers=self._operator_headers(),
        )
        _status, data = self._get_json("/v1/meta/registry", headers=self._operator_headers())
        ids = [contract["contract_id"] for contract in data["contracts"]]
        self.assertIn(candidate_id, ids)

    def test_promotion_changes_rsi_from_unity(self) -> None:
        _status, before = self._get_json("/v1/rsi/latest", headers=self._public_headers())
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
            headers=self._operator_headers(),
        )
        _status, after = self._get_json("/v1/rsi/latest", headers=self._public_headers())
        self.assertLess(after["rsi"], 1.0)

    def test_audit_trail_records_every_decision(self) -> None:
        _status, before = self._get_json("/v1/admin/promotion/audit", headers=self._operator_headers())
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
            headers=self._operator_headers(),
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
            headers=self._operator_headers(),
        )
        _status, after = self._get_json("/v1/admin/promotion/audit", headers=self._operator_headers())
        self.assertEqual(len(after), count_before + 2)

    def test_sources_markets_returns_all_active_sources(self) -> None:
        _status, data = self._get_json("/v1/sources/markets", headers=self._operator_headers())
        sources = {market["source"] for market in data}
        self.assertIn("polymarket", sources)

    def test_public_meta_requires_api_key(self) -> None:
        status, payload = self._get_json("/v1/meta")
        self.assertEqual(401, status)
        self.assertEqual("unauthorized", payload["error"])

    def test_admin_queue_requires_operator_key(self) -> None:
        status, payload = self._get_json("/v1/admin/promotion/queue", headers=self._public_headers())
        self.assertEqual(401, status)
        self.assertEqual("unauthorized", payload["error"])

    def test_public_meta_reports_version_and_counts(self) -> None:
        status, payload = self._get_json("/v1/meta", headers=self._public_headers())
        self.assertEqual(200, status)
        self.assertEqual("0.6.4", payload["version"])
        self.assertIn("governed_families", payload)
        self.assertIn("active_signals", payload)
        self.assertIn("current_rsi", payload)

    def test_public_registry_returns_governed_rows(self) -> None:
        status, payload = self._get_json("/v1/registry/governed", headers=self._public_headers())
        self.assertEqual(200, status)
        self.assertIn("count", payload)
        self.assertIn("families", payload)
        self.assertEqual(payload["count"], len(payload["families"]))

    def test_public_rsi_endpoint_rate_limits(self) -> None:
        api_app.SignalAPIHandler.public_rate_limits["/v1/rsi/latest"] = 1
        api_app.SignalAPIHandler._rate_limit_state.clear()
        first_status, _first = self._get_json("/v1/rsi/latest", headers=self._public_headers())
        second_status, second = self._get_json("/v1/rsi/latest", headers=self._public_headers())
        self.assertEqual(200, first_status)
        self.assertEqual(429, second_status)
        self.assertEqual("rate_limited", second["error"])

    def test_enterprise_endpoints_require_enterprise_key(self) -> None:
        status, payload = self._get_json("/v1/enterprise/rsi/history", headers=self._public_headers())
        self.assertEqual(401, status)
        self.assertEqual("unauthorized", payload["error"])

    def test_enterprise_rsi_history_returns_filtered_rows(self) -> None:
        latest_dir = self.root / "outputs" / "latest"
        latest_dir.mkdir(parents=True, exist_ok=True)
        (latest_dir / "daily_rsi_decomposition.csv").write_text(
            "\n".join(
                [
                    "date,total_hazard,rsi,rsi_drag,active_event_count,dominant_event_id,dominant_category,dominant_theme,probability_component_hazard,severity_component_hazard,velocity_component_hazard,persistence_component_hazard,probability_share_of_hazard,severity_share_of_hazard,velocity_share_of_hazard,persistence_share_of_hazard",
                    "2026-03-24,1.2,0.9,0.1,2,event_a,Kinetic,geopolitical,0.1,0.3,0.4,0.4,0.1,0.25,0.33,0.33",
                    "2026-03-25,2.4,0.7,0.3,3,event_b,Monetary,monetary_policy,0.2,0.6,0.7,0.9,0.08,0.25,0.29,0.38",
                ]
            ),
            encoding="utf-8",
        )

        status, payload = self._get_json(
            "/v1/enterprise/rsi/history?start=2026-03-25&limit=1",
            headers=self._enterprise_headers(),
        )
        self.assertEqual(200, status)
        self.assertEqual(1, len(payload))
        self.assertEqual("2026-03-25", payload[0]["date"])
        self.assertEqual("event_b", payload[0]["dominant_event_id"])

    def test_operator_key_can_access_enterprise_history(self) -> None:
        latest_dir = self.root / "outputs" / "latest"
        latest_dir.mkdir(parents=True, exist_ok=True)
        (latest_dir / "daily_rsi_decomposition.csv").write_text(
            "\n".join(
                [
                    "date,total_hazard,rsi,rsi_drag,active_event_count,dominant_event_id,dominant_category,dominant_theme,probability_component_hazard,severity_component_hazard,velocity_component_hazard,persistence_component_hazard,probability_share_of_hazard,severity_share_of_hazard,velocity_share_of_hazard,persistence_share_of_hazard",
                    "2026-03-26,3.1,0.5,0.2,4,event_z,Kinetic,geopolitical,0.4,0.8,1.0,0.9,0.13,0.26,0.32,0.29",
                ]
            ),
            encoding="utf-8",
        )

        status, payload = self._get_json("/v1/enterprise/rsi/history", headers=self._operator_headers())
        self.assertEqual(200, status)
        self.assertEqual(1, len(payload))
        self.assertEqual("event_z", payload[0]["dominant_event_id"])

    def test_enterprise_themes_latest_returns_current_theme_groups(self) -> None:
        _write_json(
            self.root / "outputs" / "signals" / "rsi_snapshot.json",
            {
                "asof": "2026-03-26",
                "theme_hazard_shares": {"geopolitical": 0.75, "monetary_policy": 0.25},
                "events": [
                    {
                        "event_family_id": "geo_family",
                        "title": "Geo event",
                        "structural_theme": "geopolitical",
                        "category": "Kinetic",
                        "source": "polymarket",
                        "market_id": "m1",
                        "selected_probability_governed": 0.8,
                        "hazard_contribution": 3.0,
                        "theme_cap_applied": True,
                        "calibration_applied": "none",
                    },
                    {
                        "event_family_id": "mon_family",
                        "title": "Mon event",
                        "structural_theme": "monetary_policy",
                        "category": "Monetary",
                        "source": "polymarket",
                        "market_id": "m2",
                        "selected_probability_governed": 0.3,
                        "hazard_contribution": 1.0,
                        "theme_cap_applied": False,
                        "calibration_applied": "becker",
                    },
                ],
            },
        )
        _write_json(
            self.root / "outputs" / "signals" / "signal_snapshots.json",
            [
                {"event_family_id": "geo_family", "quality_score": 0.7, "candidate_count": 2, "source_options": ["polymarket"]},
                {"event_family_id": "mon_family", "quality_score": 0.8, "candidate_count": 1, "source_options": ["polymarket"]},
            ],
        )

        status, payload = self._get_json("/v1/enterprise/themes/latest", headers=self._enterprise_headers())
        self.assertEqual(200, status)
        self.assertEqual(2, len(payload))
        self.assertEqual("geopolitical", payload[0]["theme"])
        self.assertEqual("geo_family", payload[0]["dominant_event_family_id"])

    def test_enterprise_families_latest_returns_breakdown(self) -> None:
        family_id = "geo_family"
        _write_json(
            self.root / "outputs" / "signals" / "family_signal_book.json",
            [
                {
                    "event_family_id": family_id,
                    "title": "Geo family",
                    "structural_theme": "geopolitical",
                    "category": "Kinetic",
                    "selection_state": "selected",
                    "discovered": False,
                    "governance_source": "signal_registry",
                }
            ],
        )
        _write_json(
            self.root / "outputs" / "signals" / "canonical_event_families.json",
            [{"event_family_id": family_id, "linked_markets": [{"market_id": "m1"}]}],
        )
        _write_json(
            self.root / "outputs" / "signals" / "signal_snapshots.json",
            [
                {
                    "event_family_id": family_id,
                    "selected_source": "polymarket",
                    "selected_market_id": "m1",
                    "selected_probability_governed": 0.8,
                    "selected_probability_raw": 0.82,
                    "quality_score": 0.75,
                    "candidate_count": 3,
                    "source_options": ["polymarket"],
                    "calibration_applied": "none",
                }
            ],
        )

        status, payload = self._get_json(
            "/v1/enterprise/families/latest?selection_state=selected",
            headers=self._enterprise_headers(),
        )
        self.assertEqual(200, status)
        self.assertEqual(1, len(payload))
        self.assertEqual("polymarket", payload[0]["selected_source"])
        self.assertEqual(1, payload[0]["linked_market_count"])


if __name__ == "__main__":
    unittest.main()
