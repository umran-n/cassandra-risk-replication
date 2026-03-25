from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.source_sync import collect_source_catalogs, write_source_outputs  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    refresh = "--refresh" in argv
    _registry, source_markets, source_status_rows = collect_source_catalogs(ROOT, refresh=refresh)
    write_source_outputs(ROOT, source_markets, source_status_rows)
    print("Source sync complete.")
    for row in source_status_rows:
        print(f"{row['source']}: reachable={row['reachable']} markets={row['market_count']} notes={row['notes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
