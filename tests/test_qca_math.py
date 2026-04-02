from __future__ import annotations

import math
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from qca_replication.features import _amazon_internal_particle, compute_qii, compute_theta
from qca_replication.models import fit_coherence_curve, spectral_entropy_from_matrix
from qca_replication.utils import map_announcement_to_t0, parse_datetime


class QCAMathTests(unittest.TestCase):
    def test_t0_mapping_respects_after_hours(self) -> None:
        trading_dates = [date(2024, 5, 1), date(2024, 5, 2), date(2024, 5, 3)]
        after_close = parse_datetime("2024-05-02T20:30:00+00:00")
        pre_market = parse_datetime("2024-05-02T11:00:00+00:00")
        self.assertEqual(map_announcement_to_t0(after_close, trading_dates), date(2024, 5, 3))
        self.assertEqual(map_announcement_to_t0(pre_market, trading_dates), date(2024, 5, 2))

    def test_theta_formula_matches_user_contract(self) -> None:
        theta = compute_theta(0.9, 0.7, 0.8, h_t=1.0)
        self.assertAlmostEqual(theta, 36.0, places=6)

    def test_qii_harmonic_form_is_bounded(self) -> None:
        self.assertAlmostEqual(compute_qii(0.2, 0.2, 0.0), 1.0, places=6)
        self.assertAlmostEqual(compute_qii(0.2, 0.2, 180.0), -1.0, places=6)

    def test_amazon_internal_particle_uses_margin_and_capex_deltas(self) -> None:
        company_facts = {
            "facts": {
                "dei": {},
                "us-gaap": {
                    "RevenueFromContractWithCustomerExcludingAssessedTax": {
                        "units": {
                            "USD": [
                                {"start": "2023-01-01", "end": "2023-03-31", "val": 100.0, "filed": "2023-04-30"},
                                {"start": "2023-04-01", "end": "2023-06-30", "val": 100.0, "filed": "2023-07-30"},
                                {"start": "2023-07-01", "end": "2023-09-30", "val": 100.0, "filed": "2023-10-30"},
                                {"start": "2023-10-01", "end": "2023-12-31", "val": 100.0, "filed": "2024-01-30"},
                                {"start": "2024-01-01", "end": "2024-03-31", "val": 110.0, "filed": "2024-04-30"}
                            ]
                        }
                    },
                    "OperatingIncomeLoss": {
                        "units": {
                            "USD": [
                                {"start": "2023-01-01", "end": "2023-03-31", "val": 10.0, "filed": "2023-04-30"},
                                {"start": "2023-04-01", "end": "2023-06-30", "val": 10.0, "filed": "2023-07-30"},
                                {"start": "2023-07-01", "end": "2023-09-30", "val": 10.0, "filed": "2023-10-30"},
                                {"start": "2023-10-01", "end": "2023-12-31", "val": 10.0, "filed": "2024-01-30"},
                                {"start": "2024-01-01", "end": "2024-03-31", "val": 16.5, "filed": "2024-04-30"}
                            ]
                        }
                    },
                    "PaymentsToAcquirePropertyPlantAndEquipment": {
                        "units": {
                            "USD": [
                                {"start": "2023-01-01", "end": "2023-03-31", "val": 8.0, "filed": "2023-04-30"},
                                {"start": "2023-04-01", "end": "2023-06-30", "val": 8.0, "filed": "2023-07-30"},
                                {"start": "2023-07-01", "end": "2023-09-30", "val": 8.0, "filed": "2023-10-30"},
                                {"start": "2023-10-01", "end": "2023-12-31", "val": 8.0, "filed": "2024-01-30"},
                                {"start": "2024-01-01", "end": "2024-03-31", "val": 12.0, "filed": "2024-04-30"}
                            ]
                        }
                    }
                }
            }
        }
        particle = _amazon_internal_particle(company_facts, market_cap=1000.0, asof=date(2024, 5, 1))
        self.assertIsNotNone(particle)
        self.assertGreater(particle or 0.0, 0.0)

    def test_coherence_fit_recovers_tau_reasonably(self) -> None:
        config = {
            "coherence": {
                "tau_min": 0.5,
                "tau_max": 100.0,
                "tau_step": 0.5,
                "min_post_days": 60,
                "min_fit_r2": 0.8
            }
        }
        horizons = [1, 2, 3, 5, 10, 20, 40, 60, 90, 120]
        tau_true = 20.0
        car_0 = 0.08
        car_inf = 0.01
        cars = [car_inf + (car_0 - car_inf) * math.exp(-h / tau_true) for h in horizons]
        fit = fit_coherence_curve(horizons, cars, config)
        self.assertIsNotNone(fit)
        self.assertAlmostEqual(fit["tau"], tau_true, delta=2.0)

    def test_spectral_entropy_identity_matrix(self) -> None:
        matrix = [[1.0 if row == col else 0.0 for col in range(5)] for row in range(5)]
        probabilities, entropy, d_eff = spectral_entropy_from_matrix(matrix)
        self.assertEqual(len(probabilities), 5)
        self.assertAlmostEqual(entropy, math.log(5, 2), places=3)
        self.assertAlmostEqual(d_eff, 5.0, places=3)


if __name__ == "__main__":
    unittest.main()
