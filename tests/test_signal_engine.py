from __future__ import annotations

import random
from pathlib import Path
import unittest

from cassandra_risk.signal_contract import SignalContract, Source
from cassandra_risk.signal_engine import build_signal_book, select_family_representative
from cassandra_risk.source_registry import load_source_registry


ROOT = Path(__file__).resolve().parents[1]


def _make_contract(
    native_id: str,
    title: str,
    theme: str,
    category: str,
    probability: float,
    resolves_at: str,
    *,
    aggregation_policy: str | None = None,
    volume_usd: float = 100000.0,
) -> SignalContract:
    final_aggregation_policy = aggregation_policy or ("weighted_average" if theme == "geopolitical" else "max")
    return SignalContract(
        contract_id=f"polymarket::{native_id}",
        source=Source.POLYMARKET,
        provenance_tier="live_ingested",
        question_text=title,
        structural_theme=theme,
        proxy_family_id=None,
        aggregation_policy=final_aggregation_policy,
        probability_raw=probability,
        probability_calibrated=probability,
        efficiency_gap_applied=0.0,
        created_at="2026-03-01",
        resolves_at=resolves_at,
        resolved_outcome=None,
        volume_usd=volume_usd,
        quality_score=0.8,
        is_binary=True,
        is_macro_relevant=True,
        last_updated="2026-03-26T00:00:00Z",
        snapshot_timestamp="2026-03-26T00:00:00Z",
        category=category,
        native_id=native_id,
        status="open",
    )


class SignalEngineTests(unittest.TestCase):
    def test_select_family_representative_max_is_deterministic_regardless_of_input_order(self) -> None:
        contracts = [
            _make_contract("pm1", "Fed risk one", "monetary_policy", "Monetary", 0.72, "2026-06-30", aggregation_policy="max"),
            _make_contract("pm2", "Fed risk two", "monetary_policy", "Monetary", 0.41, "2026-06-30", aggregation_policy="max"),
            _make_contract("pm3", "Fed risk three", "monetary_policy", "Monetary", 0.58, "2026-06-30", aggregation_policy="max"),
        ]
        for _ in range(10):
            random.shuffle(contracts)
            winner = select_family_representative(contracts, "max")
            self.assertAlmostEqual(winner.probability_calibrated or 0.0, 0.72)

    def test_select_family_representative_weighted_average_prefers_highest_volume(self) -> None:
        winner = select_family_representative(
            [
                _make_contract("pm1", "Geo one", "geopolitical", "Kinetic", 0.85, "2026-06-30", aggregation_policy="weighted_average", volume_usd=150000.0),
                _make_contract("pm2", "Geo two", "geopolitical", "Kinetic", 0.42, "2026-06-30", aggregation_policy="weighted_average", volume_usd=950000.0),
                _make_contract("pm3", "Geo three", "geopolitical", "Kinetic", 0.99, "2026-06-30", aggregation_policy="weighted_average", volume_usd=250000.0),
            ],
            "weighted_average",
        )
        self.assertEqual("pm2", winner.native_id)

    def test_select_family_representative_mixed_policy_raises(self) -> None:
        with self.assertRaises(ValueError):
            select_family_representative(
                [
                    _make_contract("pm1", "Mixed one", "geopolitical", "Kinetic", 0.72, "2026-06-30", aggregation_policy="max"),
                    _make_contract("pm2", "Mixed two", "geopolitical", "Kinetic", 0.41, "2026-06-30", aggregation_policy="weighted_average"),
                ],
                "max",
            )

    def test_build_signal_book_uses_family_aggregation_policy(self) -> None:
        registry = load_source_registry(ROOT)
        families = [
            {
                "event_family_id": "iran_family",
                "title": "Another Israeli military action against Iran in 2026?",
                "structural_theme": "geopolitical",
                "category": "Kinetic",
                "aggregation_policy": "weighted_average",
                "governance_source": "signal_registry",
                "proxy_family_id": "iran_family",
                "source_candidates": [],
                "discovered": False,
                "linked_markets": [
                    _make_contract("pm_low", "Lower probability, higher volume", "geopolitical", "Kinetic", 0.35, "2026-06-30", aggregation_policy="weighted_average", volume_usd=900000.0),
                    _make_contract("pm_hot", "Hot but thinner", "geopolitical", "Kinetic", 0.95, "2026-06-30", aggregation_policy="weighted_average", volume_usd=120000.0),
                ],
            }
        ]
        family_rows, snapshots, _ = build_signal_book(families, registry, ROOT)
        self.assertEqual("weighted_average", family_rows[0]["aggregation_policy"])
        self.assertEqual("pm_low", snapshots[0]["selected_market_id"])

    def test_build_signal_book_keeps_discovered_candidates_out_of_governed_snapshots(self) -> None:
        registry = load_source_registry(ROOT)
        families = [
            {
                "event_family_id": "rate_hike_shock_2022",
                "title": "Aggressive Fed tightening risk",
                "structural_theme": "monetary_policy",
                "category": "Monetary",
                "aggregation_policy": "max",
                "governance_source": "seed_file",
                "proxy_family_id": "rate_hike_shock_2022",
                "source_candidates": [],
                "discovered": False,
                "linked_markets": [
                    _make_contract("pm1", "Aggressive Fed tightening risk", "monetary_policy", "Monetary", 0.9, "2026-06-30")
                ],
            },
            {
                "event_family_id": "discovered_polymarket_1",
                "title": "US strikes on Iran in 2026?",
                "structural_theme": "geopolitical",
                "category": "Kinetic",
                "aggregation_policy": "weighted_average",
                "governance_source": "autonomous_discovery",
                "proxy_family_id": "discovered_geopolitical_polymarket",
                "source_candidates": [],
                "discovered": True,
                "linked_markets": [
                    _make_contract("pm2", "US strikes on Iran in 2026?", "geopolitical", "Kinetic", 0.4, "2026-09-30")
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
