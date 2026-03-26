from __future__ import annotations

from datetime import datetime, timezone
import unittest

from cassandra_risk.signal_contract import SignalContract, Source


def make_test_contract(**overrides) -> SignalContract:
    payload = {
        "contract_id": "polymarket::fed-cut-jun-2026",
        "source": Source.POLYMARKET,
        "provenance_tier": "live_ingested",
        "question_text": "Will the Fed cut rates in June 2026?",
        "structural_theme": "monetary_policy",
        "proxy_family_id": "fed_rate_2026_q2",
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
        "category": "Monetary",
        "native_id": "fed-cut-jun-2026",
        "status": "open",
    }
    payload.update(overrides)
    return SignalContract(**payload)


class TestSignalContractSchema(unittest.TestCase):
    def test_contract_id_format(self) -> None:
        c = make_test_contract()
        source, native = c.contract_id.split("::")
        self.assertIn(source, ["polymarket", "kalshi", "metaculus", "manifold"])
        self.assertTrue(len(native) > 0)

    def test_probability_raw_bounded(self) -> None:
        c = make_test_contract()
        self.assertGreaterEqual(c.probability_raw or 0.0, 0.0)
        self.assertLessEqual(c.probability_raw or 0.0, 1.0)

    def test_probability_calibrated_bounded(self) -> None:
        c = make_test_contract()
        self.assertGreaterEqual(c.probability_calibrated or 0.0, 0.0)
        self.assertLessEqual(c.probability_calibrated or 0.0, 1.0)

    def test_calibrated_equals_raw_when_no_gap_applied(self) -> None:
        c = make_test_contract(efficiency_gap_applied=0.0, probability_raw=0.42, probability_calibrated=0.1)
        self.assertAlmostEqual(c.probability_raw or 0.0, c.probability_calibrated or 0.0, places=6)

    def test_structural_theme_is_valid(self) -> None:
        c = make_test_contract()
        self.assertIn(
            c.structural_theme,
            {
                "monetary_policy",
                "geopolitical",
                "fiscal_debt",
                "electoral",
                "systemic_credit",
                "trade_technology",
            },
        )

    def test_provenance_tier_is_valid(self) -> None:
        c = make_test_contract()
        self.assertIn(c.provenance_tier, {"paper_seeded", "archive_recovered", "live_ingested"})

    def test_aggregation_policy_is_valid(self) -> None:
        c = make_test_contract()
        self.assertIn(c.aggregation_policy, ["max", "weighted_average"])

    def test_resolves_at_after_created_at(self) -> None:
        c = make_test_contract()
        self.assertGreater(c.resolves_at, c.created_at)

    def test_resolved_outcome_is_none_or_bool(self) -> None:
        c = make_test_contract()
        self.assertIn(c.resolved_outcome, [True, False, None])

    def test_volume_usd_non_negative(self) -> None:
        c = make_test_contract()
        self.assertGreaterEqual(c.volume_usd, 0.0)

    def test_quality_score_bounded(self) -> None:
        c = make_test_contract()
        self.assertGreaterEqual(c.quality_score, 0.0)
        self.assertLessEqual(c.quality_score, 1.0)

    def test_snapshot_timestamp_is_datetime(self) -> None:
        c = make_test_contract()
        self.assertIsInstance(c.snapshot_timestamp, datetime)
        self.assertEqual(c.snapshot_timestamp.tzinfo, timezone.utc)


if __name__ == "__main__":
    unittest.main()
