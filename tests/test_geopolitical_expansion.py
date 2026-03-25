from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.geopolitical_expansion import (  # noqa: E402
    GEOPOLITICAL_EXPANSION_SELECTIONS,
    build_geopolitical_expansion_rows,
)


class GeopoliticalExpansionTests(unittest.TestCase):
    def test_build_geopolitical_expansion_rows_uses_all_selected_markets(self) -> None:
        candidates = []
        for index, selection in enumerate(GEOPOLITICAL_EXPANSION_SELECTIONS, start=1):
            candidates.append(
                {
                    "market_id": selection["market_id"],
                    "title": f"Candidate {index}",
                    "question": f"Candidate {index}",
                    "structural_theme": "geopolitical",
                    "resolution_date": f"2024-0{index}-01",
                    "peak_probability": 0.5,
                    "volume": 600000 + index,
                    "quality_score": 0.6 + index / 100.0,
                }
            )

        rows = build_geopolitical_expansion_rows(candidates)
        self.assertEqual(len(rows), len(GEOPOLITICAL_EXPANSION_SELECTIONS))
        self.assertTrue(all(row["theme"] == "geopolitical" for row in rows))
        self.assertTrue(all(row["source"] == "polymarket" for row in rows))
        self.assertTrue(all(row["approval_status"] == "APPROVED" for row in rows))
        self.assertTrue(all(row["proxy_family_id"].startswith("polymarket_geopolitical_") for row in rows))
        self.assertTrue(all(row["calibration_subbucket"] for row in rows))
        self.assertTrue(all(row["horizon_profile"] for row in rows))


if __name__ == "__main__":
    unittest.main()
