from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.final_curation import (  # noqa: E402
    build_final_universe,
    build_universe_summary,
    load_curated_rows,
    write_approved_json,
    write_universe_summary,
)


def main() -> int:
    source_path = ROOT / "data" / "curated" / "curated_final_universe.csv"
    approved_path = ROOT / "data" / "curated" / "polymarket_approved.json"
    summary_path = ROOT / "data" / "curated" / "universe_summary.md"

    source_rows = load_curated_rows(source_path)
    approved_rows, dropped_rows = build_final_universe(source_rows)

    write_approved_json(approved_path, approved_rows)
    write_universe_summary(
        summary_path,
        build_universe_summary(
            source_rows=source_rows,
            approved_rows=approved_rows,
            dropped_rows=dropped_rows,
        ),
    )

    print(f"Loaded {len(source_rows)} source rows from {source_path}")
    print(f"Wrote {len(approved_rows)} approved rows to {approved_path}")
    print(f"Dropped {len(dropped_rows)} Israel-arc variants")
    print(f"Wrote summary to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
