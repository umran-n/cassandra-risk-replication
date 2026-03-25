from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.config import load_json  # noqa: E402
from cassandra_risk.geopolitical_expansion import (  # noqa: E402
    build_geopolitical_expansion_rows,
    render_geopolitical_expansion_summary,
    write_geopolitical_expansion_json,
    write_selection_audit_csv,
)


def main() -> int:
    candidates = load_json(ROOT / "data" / "candidates" / "polymarket_candidates.json")
    rows = build_geopolitical_expansion_rows(candidates)

    curated_path = ROOT / "data" / "curated" / "polymarket_geopolitical_expansion.json"
    summary_path = ROOT / "data" / "curated" / "polymarket_geopolitical_expansion_summary.md"
    audit_path = ROOT / "outputs" / "expansion" / "geopolitical_selection_audit.csv"

    write_geopolitical_expansion_json(curated_path, rows)
    render_geopolitical_expansion_summary(summary_path, rows)
    write_selection_audit_csv(audit_path, rows)

    print(f"Wrote {len(rows)} curated geopolitical expansion rows to {curated_path}")
    print(f"Wrote summary to {summary_path}")
    print(f"Wrote selection audit to {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
