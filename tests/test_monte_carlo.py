from __future__ import annotations

import random
import unittest

from cassandra_risk.monte_carlo import block_bootstrap_indices, monte_carlo_summary_rows


class MonteCarloTests(unittest.TestCase):
    def test_block_bootstrap_indices_respects_length_and_bounds(self) -> None:
        indices = block_bootstrap_indices(37, 5, random.Random(7))
        self.assertEqual(len(indices), 37)
        self.assertTrue(all(0 <= idx < 37 for idx in indices))

    def test_summary_rows_compute_sortino_p_value(self) -> None:
        observed = {
            "sortino": 0.33,
            "cagr": 0.07,
            "mdd": -0.33,
            "downside_deviation": 0.14,
        }
        samples = {
            "sortino": [0.10, 0.20, 0.40, 0.50],
            "cagr": [0.01, 0.02, 0.03, 0.04],
            "mdd": [-0.40, -0.35, -0.30, -0.25],
            "downside_deviation": [0.10, 0.12, 0.14, 0.16],
        }
        rows = monte_carlo_summary_rows(observed, samples)
        by_metric = {row["metric"]: row for row in rows}
        self.assertAlmostEqual(by_metric["sortino"]["p_value"], 0.5)
        self.assertEqual(by_metric["cagr"]["p_value"], "")
        self.assertAlmostEqual(by_metric["sortino"]["ci_lower_95"], 0.1075)
        self.assertAlmostEqual(by_metric["sortino"]["ci_upper_95"], 0.4925)


if __name__ == "__main__":
    unittest.main()
