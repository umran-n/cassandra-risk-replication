from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from qca_replication.pipeline import run_pipeline


def _business_days(start: date, end: date) -> list[date]:
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _price_series(start: date, end: date, base: float, drift: float, amplitude: float) -> dict:
    rows = []
    close = base
    for idx, current in enumerate(_business_days(start, end)):
        close *= 1.0 + drift + amplitude * math.sin(idx / 9.0)
        rows.append({"date": current.isoformat(), "close": round(close, 4), "adjclose": round(close, 4)})
    return {"rows": rows, "dividends": [], "splits": []}


def _fixture_bundle() -> dict:
    start = date(2024, 1, 2)
    end = date(2025, 2, 28)
    bundle = {
        "price_history": {
            "AAPL": _price_series(start, end, 180.0, 0.0008, 0.0015),
            "AMZN": _price_series(start, end, 150.0, 0.0010, 0.0018),
            "SPY": _price_series(start, end, 500.0, 0.0005, 0.0008),
            "XLK": _price_series(start, end, 210.0, 0.0006, 0.0010),
            "^VIX": _price_series(start, end, 18.0, 0.0001, 0.0025)
        },
        "company_facts": {
            "AAPL": {
                "facts": {
                    "dei": {
                        "EntityCommonStockSharesOutstanding": {
                            "units": {
                                "shares": [
                                    {"end": "2024-04-15", "val": 16000000000, "filed": "2024-04-15"},
                                    {"end": "2024-12-31", "val": 15800000000, "filed": "2025-01-15"}
                                ]
                            }
                        }
                    },
                    "us-gaap": {
                        "PaymentsForRepurchaseOfCommonStock": {
                            "units": {
                                "USD": [
                                    {"start": "2024-01-01", "end": "2024-03-31", "val": 12000000000, "filed": "2024-04-15"},
                                    {"start": "2024-04-01", "end": "2024-06-30", "val": 11000000000, "filed": "2024-07-15"},
                                    {"start": "2024-10-01", "end": "2024-12-31", "val": 13000000000, "filed": "2025-01-15"}
                                ]
                            }
                        }
                    }
                }
            },
            "AMZN": {
                "facts": {
                    "dei": {
                        "EntityCommonStockSharesOutstanding": {
                            "units": {
                                "shares": [
                                    {"end": "2024-07-15", "val": 10500000000, "filed": "2024-07-15"},
                                    {"end": "2025-01-15", "val": 10450000000, "filed": "2025-01-15"}
                                ]
                            }
                        }
                    },
                    "us-gaap": {
                        "RevenueFromContractWithCustomerExcludingAssessedTax": {
                            "units": {
                                "USD": [
                                    {"start": "2023-10-01", "end": "2023-12-31", "val": 170000000000, "filed": "2024-01-31"},
                                    {"start": "2024-01-01", "end": "2024-03-31", "val": 180000000000, "filed": "2024-04-30"},
                                    {"start": "2024-04-01", "end": "2024-06-30", "val": 185000000000, "filed": "2024-07-31"},
                                    {"start": "2024-07-01", "end": "2024-09-30", "val": 190000000000, "filed": "2024-10-31"},
                                    {"start": "2024-10-01", "end": "2024-12-31", "val": 205000000000, "filed": "2025-01-31"}
                                ]
                            }
                        },
                        "OperatingIncomeLoss": {
                            "units": {
                                "USD": [
                                    {"start": "2023-10-01", "end": "2023-12-31", "val": 14000000000, "filed": "2024-01-31"},
                                    {"start": "2024-01-01", "end": "2024-03-31", "val": 15000000000, "filed": "2024-04-30"},
                                    {"start": "2024-04-01", "end": "2024-06-30", "val": 16500000000, "filed": "2024-07-31"},
                                    {"start": "2024-07-01", "end": "2024-09-30", "val": 17500000000, "filed": "2024-10-31"},
                                    {"start": "2024-10-01", "end": "2024-12-31", "val": 23000000000, "filed": "2025-01-31"}
                                ]
                            }
                        },
                        "PaymentsToAcquirePropertyPlantAndEquipment": {
                            "units": {
                                "USD": [
                                    {"start": "2023-10-01", "end": "2023-12-31", "val": 12000000000, "filed": "2024-01-31"},
                                    {"start": "2024-01-01", "end": "2024-03-31", "val": 13000000000, "filed": "2024-04-30"},
                                    {"start": "2024-04-01", "end": "2024-06-30", "val": 15000000000, "filed": "2024-07-31"},
                                    {"start": "2024-07-01", "end": "2024-09-30", "val": 18000000000, "filed": "2024-10-31"},
                                    {"start": "2024-10-01", "end": "2024-12-31", "val": 25000000000, "filed": "2025-01-31"}
                                ]
                            }
                        }
                    }
                }
            }
        },
        "management_texts": {
            "AAPL": [
                {"date": "2024-04-10", "source_type": "ir_press_release", "text": "Strong demand, disciplined capital allocation, durable growth and confidence in returns."},
                {"date": "2025-01-10", "source_type": "ir_press_release", "text": "Efficient execution, strong opportunity, constructive demand and support for shareholder returns."}
            ],
            "AMZN": [
                {"date": "2024-07-20", "source_type": "ir_press_release", "text": "AI infrastructure investment accelerates growth, improves efficiency and expands operating leverage."},
                {"date": "2025-01-12", "source_type": "ir_press_release", "text": "Disciplined reallocation into AI capacity supports durable growth and strong long-term opportunity."}
            ]
        }
    }
    bundle["price_history"]["AAPL"]["dividends"] = [
        {"date": "2024-02-15", "amount": 0.24},
        {"date": "2024-05-15", "amount": 0.25},
        {"date": "2024-08-15", "amount": 0.25},
        {"date": "2024-11-15", "amount": 0.26}
    ]
    return bundle


def _test_config(base_dir: Path, bundle_path: Path, overlay_path: Path, output_dir: Path) -> dict:
    return {
        "data_tier": "public_proxy",
        "sample": {
            "start": "2024-01-01",
            "end": "2025-01-31",
            "lookback_start": "2023-10-01",
            "oos_start": "2025-01-01"
        },
        "sec": {"user_agent": "Codex QCA Tests openai@example.com"},
        "market_data": {
            "provider": "Fixture",
            "chart_url_template": "unused",
            "options_url_template": "unused",
            "market_symbol": "SPY",
            "sector_symbol": "XLK",
            "vix_symbol": "^VIX"
        },
        "firms": [
            {"ticker": "AAPL", "name": "Apple Inc.", "cik": "0000320193", "archetype": "Particle-Dominant", "target_count": 2, "particle_variant": "standard"},
            {"ticker": "AMZN", "name": "Amazon.com, Inc.", "cik": "0001018724", "archetype": "Transducer", "target_count": 2, "particle_variant": "internal_reallocation"}
        ],
        "discovery": {
            "manual_overlay_path": str(overlay_path),
            "forms": [],
            "keyword_groups": {"buyback": [], "dividend": [], "split": [], "internal_reallocation": []},
            "selection_score_threshold": 4
        },
        "management_sentiment": {
            "lookback_days": 120,
            "model_preference": "finbert",
            "fallback_model": "lexical_public_proxy",
            "positive_terms": ["strong", "durable", "growth", "confidence", "efficient", "constructive", "opportunity", "support", "accelerates", "improves"],
            "negative_terms": ["risk", "challenge", "pressure", "weakness", "uncertain"]
        },
        "market_sentiment": {"price_proxy_window_days": 20, "scale": 0.15},
        "options_sentiment": {"realized_skew_window_days": 20, "min_expiry_offset_days": 20},
        "theta": {"h_t_default": 1.0},
        "regression": {
            "bootstrap_resamples": 100,
            "seed": 42,
            "time_splits": [
                {"name": "2024", "start": "2024-01-01", "end": "2024-12-31"},
                {"name": "2025", "start": "2025-01-01", "end": "2025-01-31"}
            ]
        },
        "coherence": {"horizons": [1, 2, 3, 5, 10, 20, 40, 60, 90, 120], "tau_min": 0.5, "tau_max": 100.0, "tau_step": 0.5, "min_post_days": 60, "min_fit_r2": 0.5},
        "entanglement": {"tail_horizon_days": 50, "catastrophic_threshold": -0.3, "major_drawdown_threshold": -0.1, "contagion_threshold": 0.1},
        "outputs": {"latest_dir": str(output_dir)},
        "fixtures": {"path": str(bundle_path), "disable_discovery": True}
    }


class QCAPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(dir=ROOT))
        self.bundle_path = self.tmpdir / "fixture_bundle.json"
        self.overlay_path = self.tmpdir / "manual_overlay.json"
        self.output_dir = self.tmpdir / "outputs"
        self.config_path = self.tmpdir / "qca_test_config.json"
        self.bundle_path.write_text(json.dumps(_fixture_bundle()), encoding="utf-8")
        self.overlay_path.write_text(
            json.dumps(
                {
                    "manual_events": [
                        {"ticker": "AAPL", "announcement_date": "2024-05-02", "event_family": "dual_announcement", "event_title": "Apple spring authorization", "authorization_amount": 110000000000, "dividend_per_share": 0.25, "manual_source_urls": ["fixture://aapl/20240502"]},
                        {"ticker": "AAPL", "announcement_date": "2025-01-30", "event_family": "dual_announcement", "event_title": "Apple winter authorization", "authorization_amount": 90000000000, "dividend_per_share": 0.26, "manual_source_urls": ["fixture://aapl/20250130"]},
                        {"ticker": "AMZN", "announcement_date": "2024-08-01", "event_family": "internal_reallocation", "event_title": "Amazon AI reallocation", "manual_source_urls": ["fixture://amzn/20240801"]},
                        {"ticker": "AMZN", "announcement_date": "2025-01-30", "event_family": "internal_reallocation", "event_title": "Amazon AI reallocation follow-up", "manual_source_urls": ["fixture://amzn/20250130"]}
                    ],
                    "exclusions": []
                }
            ),
            encoding="utf-8",
        )
        self.config_path.write_text(
            json.dumps(_test_config(self.tmpdir, self.bundle_path, self.overlay_path, self.output_dir), indent=2),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_pipeline_writes_expected_artifacts(self) -> None:
        result = run_pipeline(ROOT, self.config_path, refresh=False)
        self.assertTrue((self.output_dir / "ledger.csv").exists())
        self.assertTrue((self.output_dir / "feature_panel.csv").exists())
        self.assertTrue((self.output_dir / "coherence.csv").exists())
        self.assertTrue((self.output_dir / "entanglement.csv").exists())
        self.assertEqual(result["summary"]["data_tier"], "public_proxy")
        feature_panel = (self.output_dir / "feature_panel.csv").read_text(encoding="utf-8")
        self.assertIn("data_tier", feature_panel)
        self.assertIn("theta_source_variant", feature_panel)

    def test_cli_end_to_end(self) -> None:
        command = [sys.executable, str(ROOT / "scripts" / "run_qca_replication.py"), "--config", str(self.config_path)]
        completed = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        self.assertIn("Completed QCA closest-public replication.", completed.stdout)
        report = (self.output_dir / "report.md").read_text(encoding="utf-8")
        self.assertIn('data_tier="public_proxy"', report)
        self.assertIn("Target events", report)


if __name__ == "__main__":
    unittest.main()
