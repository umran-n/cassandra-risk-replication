from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.backtest import monthly_drawdown_episode_stats, monthly_drawdown_episodes  # noqa: E402


class RiskDecompositionTests(unittest.TestCase):
    def test_monthly_drawdown_episodes_split_by_calendar_month(self) -> None:
        dates = ["2024-01-02", "2024-01-03", "2024-02-01", "2024-02-02"]
        equity = [1.0, 0.9, 0.9, 0.81]
        episodes = monthly_drawdown_episodes(dates, equity)
        self.assertEqual(len(episodes), 2)
        self.assertAlmostEqual(episodes[0], -0.1)
        self.assertAlmostEqual(episodes[1], -0.1)

    def test_monthly_drawdown_episode_stats_reports_mean_and_worst(self) -> None:
        dates = ["2024-01-02", "2024-01-03", "2024-02-01", "2024-02-02", "2024-02-05"]
        equity = [1.0, 0.8, 0.8, 0.84, 0.7]
        stats = monthly_drawdown_episode_stats(dates, equity)
        self.assertEqual(stats["monthly_mdd_episode_count"], 2)
        self.assertAlmostEqual(stats["monthly_mdd_worst"], -0.2)
        self.assertAlmostEqual(stats["monthly_mdd_mean"], (-0.2 + -0.16666666666666663) / 2)


if __name__ == "__main__":
    unittest.main()
