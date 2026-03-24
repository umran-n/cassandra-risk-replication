from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.curation import (  # noqa: E402
    build_curator_markdown,
    build_curator_rows,
    load_candidates,
    write_curator_markdown,
    write_curator_worksheet,
)


def main() -> int:
    input_path = ROOT / "data" / "candidates" / "polymarket_candidates.json"
    output_csv = ROOT / "data" / "candidates" / "curator_worksheet.csv"
    output_md = ROOT / "data" / "candidates" / "curator_worksheet.md"

    candidates = load_candidates(input_path)
    rows = build_curator_rows(candidates)
    write_curator_worksheet(output_csv, rows)
    write_curator_markdown(output_md, build_curator_markdown(rows))

    print(f"Wrote {len(rows)} curator rows to {output_csv}")
    print(f"Wrote markdown summary to {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
