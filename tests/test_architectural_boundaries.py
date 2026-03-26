from __future__ import annotations

import ast
import inspect
import shutil
import textwrap
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from cassandra_risk.becker_calibration import BeckerCalibrationLayer
from cassandra_risk.rsi_engine import RSIEngine
from cassandra_risk.signal_contract import DefaultContractNormaliser, SignalContract, Source
from cassandra_risk.signal_engine import build_signal_book
from cassandra_risk.signal_registry import SignalRegistry
from cassandra_risk.sources.kalshi import fetch_kalshi_catalog
from cassandra_risk.sources.manifold import fetch_manifold_catalog
from cassandra_risk.sources.polymarket import fetch_polymarket_catalog


def make_test_contract(**overrides) -> SignalContract:
    payload = {
        "contract_id": "polymarket::fed-cut-jun-2026",
        "source": Source.POLYMARKET,
        "provenance_tier": "live_ingested",
        "question_text": "Will the Fed cut rates in June 2026?",
        "structural_theme": "monetary_policy",
        "proxy_family_id": "fed_rate_2026_q2",
        "aggregation_policy": "max",
        "probability_raw": 0.65,
        "probability_calibrated": 0.65,
        "efficiency_gap_applied": 0.0,
        "created_at": "2026-03-01",
        "resolves_at": "2026-06-18",
        "resolved_outcome": None,
        "volume_usd": 500000.0,
        "quality_score": 0.8,
        "is_binary": True,
        "is_macro_relevant": True,
        "last_updated": "2026-03-26T00:00:00Z",
        "snapshot_timestamp": "2026-03-26T00:00:00Z",
        "category": "Monetary",
        "native_id": "fed-cut-jun-2026",
        "status": "open",
    }
    payload.update(overrides)
    return SignalContract(**payload)


def _workspace_tempdir() -> Path:
    root = Path(__file__).resolve().parents[1] / ".tmp_tests"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"run_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class TestAdapterBoundary(unittest.TestCase):
    def test_polymarket_adapter_emits_signal_contracts(self) -> None:
        settings = {"api_base_url": "https://gamma-api.polymarket.com", "priority": 3}
        payload = [
            {
                "title": "Fed event",
                "category": "economy",
                "slug": "fed-event",
                "markets": [
                    {
                        "id": "123",
                        "question": "Will the Fed cut rates in June 2026?",
                        "active": True,
                        "closed": False,
                        "outcomes": ["Yes", "No"],
                        "probability": 0.34,
                        "volume": 2100000,
                        "liquidity": 900000,
                        "startDate": "2026-03-01",
                        "endDate": "2026-06-18",
                    }
                ],
            }
        ]
        tmpdir = _workspace_tempdir()
        try:
            with patch("cassandra_risk.sources.polymarket.fetch_json", return_value=payload):
                contracts, _status = fetch_polymarket_catalog(settings, tmpdir, refresh=True)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        self.assertTrue(contracts)
        for contract in contracts:
            self.assertIsInstance(contract, SignalContract)

    def test_no_raw_dict_reaches_rsi_engine(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry = {
            "theme_policies": {"monetary_policy": {"max_bucket_events": 15}},
            "selection_policy": {},
        }
        families = [
            {
                "event_family_id": "fed_rate_2026_q2",
                "title": "Will the Fed cut rates in June 2026?",
                "structural_theme": "monetary_policy",
                "category": "Monetary",
                "governance_source": "signal_registry",
                "discovered": False,
                "linked_markets": [make_test_contract()],
            }
        ]
        captured: dict[str, object] = {}
        original = RSIEngine.compute

        def spy(self, contracts, registry_arg, root_arg, asof_date=None):
            captured["contracts"] = contracts
            return original(self, contracts, registry_arg, root_arg, asof_date)

        with patch.object(RSIEngine, "compute", new=spy):
            build_signal_book(families, registry, root)

        for item in captured.get("contracts", []):
            self.assertNotIsInstance(item, dict, msg="Raw dict leaked into RSI engine")

    def test_rsi_engine_has_no_source_conditionals(self) -> None:
        source = textwrap.dedent(inspect.getsource(RSIEngine.compute))
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                self.assertNotEqual(
                    node.attr,
                    "source",
                    msg="RSI engine contains source conditional; adapter boundary has leaked",
                )

    def test_contract_normaliser_strips_platform_fields(self) -> None:
        raw_market = {
            "source": "polymarket",
            "market_id": "abc123",
            "title": "Will the Fed cut rates in June 2026?",
            "url": "https://example.com/abc123",
            "status": "open",
            "outcome_type": "BINARY",
            "structural_theme": "monetary_policy",
            "category": "Monetary",
            "current_probability": 0.34,
            "volume_usd": 2100000.0,
            "liquidity_usd": 900000.0,
            "open_time": "2026-03-01",
            "close_time": "2026-06-18",
            "resolution_time": "2026-06-18",
            "metadata": {"condId": "native-cond", "clob_token_ids": ["yes", "no"]},
        }
        normalised = DefaultContractNormaliser().normalise(raw_market)
        self.assertIsInstance(normalised, SignalContract)
        self.assertFalse(hasattr(normalised, "condId"))
        self.assertFalse(hasattr(normalised, "clob_token_ids"))

    def test_kalshi_adapter_emits_signal_contracts(self) -> None:
        settings = {"api_base_url": "https://api.elections.kalshi.com/trade-api/v2", "priority": 2}
        payload = {
            "events": [
                {
                    "title": "Fed event",
                    "sub_title": "Rates",
                    "category": "economy",
                    "markets": [
                        {
                            "ticker": "FEDCUT-26JUN",
                            "title": "Will the Fed cut rates in June 2026?",
                            "market_type": "binary",
                            "status": "open",
                            "yes_price": 34,
                            "volume": 1500000,
                            "open_interest": 400000,
                            "open_time": "2026-03-01T00:00:00Z",
                            "expiration_time": "2026-06-18T00:00:00Z",
                        }
                    ],
                }
            ]
        }
        tmpdir = _workspace_tempdir()
        try:
            with patch("cassandra_risk.sources.kalshi.fetch_json", return_value=payload):
                contracts, _status = fetch_kalshi_catalog(settings, tmpdir, refresh=True)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        self.assertTrue(contracts)
        for contract in contracts:
            self.assertIsInstance(contract, SignalContract)

    def test_manifold_adapter_provenance_is_archive_only(self) -> None:
        settings = {"api_base_url": "https://api.manifold.markets/v0", "priority": 4}
        payload = [
            {
                "id": "m1",
                "question": "Will Russia invade Ukraine before 2027?",
                "url": "https://manifold.markets/m1",
                "isResolved": False,
                "outcomeType": "BINARY",
                "probability": 0.42,
                "volume": 10000,
                "totalLiquidity": 1000,
                "createdTime": 1764547200000,
                "closeTime": 1796083200000,
            }
        ]
        tmpdir = _workspace_tempdir()
        try:
            with patch("cassandra_risk.sources.manifold.fetch_json", return_value=payload):
                contracts, _status = fetch_manifold_catalog(settings, tmpdir, refresh=True)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        self.assertTrue(contracts)
        for contract in contracts:
            self.assertEqual(contract.provenance_tier, "archive_recovered")

    def test_signal_registry_deduplicates_cross_source(self) -> None:
        registry = SignalRegistry()
        registry.add(make_test_contract(source=Source.POLYMARKET, contract_id="polymarket::fedcut", native_id="fedcut"))
        registry.add(make_test_contract(source=Source.KALSHI, contract_id="kalshi::fedcut", native_id="fedcut", proxy_family_id="fed_rate_2026_q2"))
        families = registry.get_families()
        self.assertEqual(len(families), 1)

    def test_becker_calibration_only_modifies_calibrated_field(self) -> None:
        contract = make_test_contract(probability_raw=0.65, probability_calibrated=0.65)
        calibrated = BeckerCalibrationLayer.apply(contract)
        self.assertEqual(calibrated.probability_raw, 0.65)
        self.assertNotEqual(calibrated.probability_calibrated, calibrated.probability_raw)


if __name__ == "__main__":
    unittest.main()
