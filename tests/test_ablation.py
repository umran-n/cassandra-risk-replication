from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.ablation import (  # noqa: E402
    dominant_proxy_by_event_from_attribution_rows,
    prepare_ablation_inputs,
)
from cassandra_risk.events import normalize_proxy_metadata  # noqa: E402
from cassandra_risk.taxonomy import infer_structural_theme  # noqa: E402


class AblationTests(unittest.TestCase):
    def test_infer_structural_theme_prefers_event_mapping_for_credit_events(self) -> None:
        self.assertEqual(
            infer_structural_theme({"event_id": "svb_contagion_2023", "category": "Sovereign"}),
            "systemic_credit",
        )
        self.assertEqual(
            infer_structural_theme({"event_id": "us_debt_ceiling_2023", "category": "Sovereign"}),
            "fiscal_debt",
        )

    def test_normalize_proxy_metadata_backfills_structural_theme(self) -> None:
        normalized = normalize_proxy_metadata(
            {
                "event_id": "ukraine_invasion_2022",
                "source": "Manifold",
                "category": "Kinetic",
                "event_date": "2022-02-24",
                "resolution_date": "2022-02-24",
                "resolved_outcome": "YES",
                "analysis_bucket": "drawdown",
                "provenance": "archive_recovered",
            }
        )
        self.assertEqual(normalized["structural_theme"], "geopolitical")

    def test_prepare_ablation_inputs_supports_public_only_theme_and_event_filters(self) -> None:
        seeds = [
            {
                "event_id": "svb_contagion_2023",
                "structural_theme": "systemic_credit",
                "source": "Manual",
            },
            {
                "event_id": "us_debt_ceiling_2023",
                "structural_theme": "fiscal_debt",
                "source": "Manual",
            },
        ]
        shortlist = [
            {
                "event_id": "svb_contagion_2023",
                "market_id": "svb-market",
                "structural_theme": "systemic_credit",
                "source": "Manifold",
            },
            {
                "event_id": "china_taiwan_2024",
                "market_id": "taiwan-market",
                "structural_theme": "geopolitical",
                "source": "Manifold",
            },
        ]
        filtered_seeds, filtered_shortlist = prepare_ablation_inputs(
            seeds,
            shortlist,
            public_only=True,
            structural_theme="systemic_credit",
            removed_event_ids={"china_taiwan_2024"},
        )
        self.assertEqual(filtered_seeds, [])
        self.assertEqual(len(filtered_shortlist), 1)
        self.assertEqual(filtered_shortlist[0]["event_id"], "svb_contagion_2023")

    def test_dominant_proxy_comes_from_cumulative_hazard(self) -> None:
        attribution_rows = [
            {
                "event_id": "us_debt_ceiling_2023",
                "dominant_event_market_id": "market-a",
                "hazard_contribution": "0.40",
            },
            {
                "event_id": "us_debt_ceiling_2023",
                "dominant_event_market_id": "market-b",
                "hazard_contribution": "0.15",
            },
            {
                "event_id": "us_debt_ceiling_2023",
                "dominant_event_market_id": "market-a",
                "hazard_contribution": "0.20",
            },
        ]
        dominant = dominant_proxy_by_event_from_attribution_rows(attribution_rows)
        self.assertEqual(dominant["us_debt_ceiling_2023"], "market-a")


if __name__ == "__main__":
    unittest.main()
