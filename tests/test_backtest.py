from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.backtest import compute_cassandra_signal, compute_vol_target_positions, simulate_strategy


class BacktestTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
