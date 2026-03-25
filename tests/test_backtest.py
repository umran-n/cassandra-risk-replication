from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.backtest import (
    build_hazard_attribution,
    compute_cassandra_signal,
    compute_vol_target_positions,
    simulate_strategy,
)
from cassandra_risk.events import (
    aggregate_daily_probabilities,
    build_event_panel,
    load_polymarket_approved_universe,
    resolve_event_sources,
)


class BacktestTests(unittest.TestCase):
    def test_aggregate_daily_probabilities_defaults_to_weighted_average(self) -> None:
        rows = [
            {
                "date": "2024-01-02",
                "event_id": "event-1",
                "category": "Sovereign",
                "probability": 0.2,
                "resolution_date": "2024-02-01",
                "source_brier": 0.25,
            },
            {
                "date": "2024-01-02",
                "event_id": "event-1",
                "category": "Sovereign",
                "probability": 0.8,
                "resolution_date": "2024-02-01",
                "source_brier": 0.5,
            },
        ]
        daily = aggregate_daily_probabilities(rows)
        self.assertAlmostEqual(daily["2024-01-02"]["event-1"]["probability"], 0.4, places=6)

    def test_aggregate_daily_probabilities_supports_max_mode(self) -> None:
        rows = [
            {
                "date": "2024-01-02",
                "event_id": "event-1",
                "category": "Sovereign",
                "probability": 0.2,
                "resolution_date": "2024-02-01",
                "source_brier": 0.25,
            },
            {
                "date": "2024-01-02",
                "event_id": "event-1",
                "category": "Sovereign",
                "probability": 0.8,
                "resolution_date": "2024-02-01",
                "source_brier": 0.5,
            },
        ]
        daily = aggregate_daily_probabilities(rows, {"cassandra": {"multi_proxy_aggregation": "max"}})
        self.assertAlmostEqual(daily["2024-01-02"]["event-1"]["probability"], 0.8, places=6)

    def test_family_policy_overrides_global_aggregation_mode(self) -> None:
        rows = [
            {
                "date": "2024-01-02",
                "event_id": "event-1",
                "category": "Sovereign",
                "probability": 0.2,
                "resolution_date": "2024-02-01",
                "source_brier": 0.25,
                "proxy_family_id": "family-1",
                "proxy_relation": "orthogonal",
                "aggregation_policy": "max",
                "quality_score": 0.5,
                "question": "proxy a",
                "source": "Manifold",
            },
            {
                "date": "2024-01-02",
                "event_id": "event-1",
                "category": "Sovereign",
                "probability": 0.8,
                "resolution_date": "2024-02-01",
                "source_brier": 0.5,
                "proxy_family_id": "family-1",
                "proxy_relation": "orthogonal",
                "aggregation_policy": "max",
                "quality_score": 0.6,
                "question": "proxy b",
                "source": "Manifold",
            },
        ]
        daily = aggregate_daily_probabilities(rows, {"cassandra": {"multi_proxy_aggregation": "weighted_average"}})
        self.assertAlmostEqual(daily["2024-01-02"]["event-1"]["probability"], 0.8, places=6)
        self.assertEqual(daily["2024-01-02"]["event-1"]["family_aggregation_policy"], "max")

    def test_rsi_matches_paper_example(self) -> None:
        config = {
            "cassandra": {
                "category_weights": {"Kinetic": 10.0},
                "category_lambdas": {"Kinetic": 0.1},
                "horizon_normalizer_days": 30,
                "rebalancing_thresholds": [0.8, 0.5, 0.3]
            }
        }
        daily_events = {
            "2022-02-15": {
                "ukraine": {
                    "category": "Kinetic",
                    "probability": 0.60,
                    "resolution_date": "2022-03-17"
                }
            }
        }
        rsi, hazard, _ = compute_cassandra_signal(["2022-02-15"], daily_events, config)
        self.assertAlmostEqual(hazard[0], 5.43, places=2)
        self.assertAlmostEqual(rsi[0], 1 / 6.43, places=3)

    def test_vol_target_never_exceeds_cap(self) -> None:
        config = {"vol_target": {"lookback_days": 3, "target_vol": 0.12, "max_position": 1.0}}
        returns = [0.0, 0.001, -0.001, 0.001, -0.001, 0.001]
        positions = compute_vol_target_positions(config, returns)
        self.assertTrue(all(0.0 <= position <= 1.0 for position in positions))

    def test_trade_costs_reduce_returns_when_position_changes(self) -> None:
        result = simulate_strategy(
            dates=["2024-01-01", "2024-01-02", "2024-01-03"],
            returns=[0.0, 0.01, 0.0],
            positions=[1.0, 0.0, 0.0],
            transaction_cost_bps=5.0
        )
        self.assertLess(result["daily_returns"][2], 0.0)

    def test_daily_rsi_decomposition_sums_to_total_hazard(self) -> None:
        config = {
            "cassandra": {
                "category_weights": {"Kinetic": 10.0, "Sovereign": 8.0, "None": 0.0},
                "category_lambdas": {"Kinetic": 0.1, "Sovereign": 0.15, "None": 0.0},
                "horizon_normalizer_days": 30,
                "rebalancing_thresholds": [0.8, 0.5, 0.3],
            }
        }
        daily_events = {
            "2024-01-02": {
                "ukraine": {
                    "event_id": "ukraine",
                    "category": "Kinetic",
                    "question": "proxy a",
                    "probability": 0.6,
                    "resolution_date": "2024-01-17",
                    "proxy_family_id": "family-a",
                    "proxy_relation": "substitute",
                },
                "svb": {
                    "event_id": "svb",
                    "category": "Sovereign",
                    "question": "proxy b",
                    "probability": 0.3,
                    "resolution_date": "2024-02-01",
                    "proxy_family_id": "family-b",
                    "proxy_relation": "substitute",
                },
            }
        }
        attribution_rows, decomposition_rows = build_hazard_attribution(["2024-01-02"], daily_events, config)
        self.assertEqual(len(decomposition_rows), 1)
        total_from_events = sum(row["hazard_contribution"] for row in attribution_rows)
        total_from_components = (
            decomposition_rows[0]["probability_component_hazard"]
            + decomposition_rows[0]["severity_component_hazard"]
            + decomposition_rows[0]["velocity_component_hazard"]
            + decomposition_rows[0]["persistence_component_hazard"]
        )
        self.assertAlmostEqual(total_from_events, decomposition_rows[0]["total_hazard"], places=9)
        self.assertAlmostEqual(total_from_components, decomposition_rows[0]["total_hazard"], places=9)

    @patch("cassandra_risk.events.fetch_manifold_search_markets")
    def test_pre_event_market_replaces_manual_seed_in_v3(self, mock_search) -> None:
        mock_search.return_value = [
            {
                "id": "market-1",
                "question": "Will the 10-year Treasury rate hit 5% by the end of 2023?",
                "createdTime": 1696809600000,
            }
        ]
        seeds = [
            {
                "event_id": "oct_selloff_2023",
                "source": "Manual",
                "category": "Monetary",
                "provenance": "manual_reconstructed",
                "event_date": "2023-10-27",
                "resolution_date": "2023-10-27",
                "resolved_outcome": "YES",
                "manifold_search_terms": ["10 year treasury 5% end of 2023"],
                "manifold_selected_market_id": "market-1",
            }
        ]

        resolved_seeds, audit_rows = resolve_event_sources(
            seeds,
            ROOT,
            refresh=False,
            enable_manifold_search=True,
        )
        self.assertEqual(resolved_seeds[0]["source"], "Manifold")
        self.assertEqual(resolved_seeds[0]["market_id"], "market-1")
        self.assertEqual(audit_rows[0]["replacement_status"], "selected_pre_event_manifold_proxy")

    @patch("cassandra_risk.events.fetch_manifold_search_markets")
    def test_post_event_market_is_rejected(self, mock_search) -> None:
        mock_search.return_value = [
            {
                "id": "market-2",
                "question": "Will another top 20 bank fail before June 1, 2023?",
                "createdTime": 1678492800000,
            }
        ]
        seeds = [
            {
                "event_id": "svb_contagion_2023",
                "source": "Manual",
                "category": "Sovereign",
                "provenance": "manual_reconstructed",
                "event_date": "2023-03-10",
                "resolution_date": "2023-03-10",
                "resolved_outcome": "YES",
                "manifold_search_terms": ["Silicon Valley Bank another bank fail March 2023"],
                "manifold_selected_market_id": "market-2",
            }
        ]

        resolved_seeds, audit_rows = resolve_event_sources(
            seeds,
            ROOT,
            refresh=False,
            enable_manifold_search=True,
        )
        self.assertEqual(resolved_seeds[0]["source"], "Manual")
        self.assertEqual(audit_rows[0]["replacement_status"], "post_event_market_rejected")

    def test_load_polymarket_approved_universe_joins_histories(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            approved_path = tmp / "approved.json"
            candidates_path = tmp / "candidates.json"
            approved_path.write_text(
                """
[
  {
    "event_id": "geopolitical_test_event_2024",
    "title": "Test Event",
    "theme": "geopolitical",
    "resolution_date": "2024-01-05",
    "proxy_family_id": "polymarket_test_event_2024",
    "source": "polymarket"
  },
  {
    "event_id": "metaculus_placeholder",
    "title": "Manual Placeholder",
    "theme": "fiscal_debt",
    "resolution_date": "2024-01-05",
    "proxy_family_id": "metaculus_placeholder",
    "source": "metaculus"
  }
]
                """.strip(),
                encoding="utf-8",
            )
            candidates_path.write_text(
                """
[
  {
    "market_id": "123",
    "title": "Test Event",
    "question": "Test Event",
    "category": "Kinetic",
    "resolved_outcome": 1.0,
    "event_window_start": "2024-01-01",
    "event_window_end": "2024-01-05",
    "quality_score": 0.8,
    "probability_timeseries": [
      {"date": "2024-01-01", "probability": 0.2},
      {"date": "2024-01-02", "probability": 0.4}
    ]
  }
]
                """.strip(),
                encoding="utf-8",
            )

            seeds, audit = load_polymarket_approved_universe(approved_path, candidates_path)
            self.assertEqual(len(seeds), 1)
            self.assertEqual(seeds[0]["source"], "Polymarket")
            self.assertEqual(audit[0]["status"], "loaded_polymarket_history")
            self.assertEqual(audit[1]["status"], "skipped_no_history")

    def test_build_event_panel_supports_polymarket_histories(self) -> None:
        config = {"cassandra": {"source_brier_scores": {"Polymarket": 0.31}}}
        seeds = [
            {
                "event_id": "geopolitical_test_event_2024",
                "question": "Test Event",
                "source": "Polymarket",
                "category": "Kinetic",
                "provenance": "polymarket_curated",
                "event_date": "2024-01-05",
                "resolution_date": "2024-01-05",
                "resolved_outcome": "YES",
                "analysis_bucket": "background",
                "structural_theme": "geopolitical",
                "market_id": "123",
                "proxy_family_id": "polymarket_test_event_2024",
                "proxy_relation": "substitute",
                "aggregation_policy": "weighted_average",
                "event_window_start": "2024-01-01",
                "event_window_end": "2024-01-05",
                "quality_score": 0.8,
                "probability_timeseries": [
                    {"date": "2024-01-01", "probability": 0.2},
                    {"date": "2024-01-02", "probability": 0.4},
                ],
            }
        ]
        rows = build_event_panel(config, seeds, ROOT, refresh=False)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["source"], "Polymarket")
        self.assertAlmostEqual(rows[1]["probability"], 0.4, places=6)


if __name__ == "__main__":
    unittest.main()
