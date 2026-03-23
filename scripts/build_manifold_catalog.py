from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.config import load_json  # noqa: E402
from cassandra_risk.discovery import discover_manifold_catalog  # noqa: E402
from cassandra_risk.utils import ensure_dir, write_csv, write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Refresh cached Manifold search and bet-history data")
    args = parser.parse_args()

    config = load_json(ROOT / "config" / "backtest_config.json")
    seeds = load_json(ROOT / "data" / "seeds" / "event_seeds.json")

    raw_dir = ensure_dir(ROOT / "data" / "raw")
    processed_dir = ensure_dir(ROOT / "data" / "processed")
    curated_dir = ensure_dir(ROOT / "data" / "curated")
    output_dir = ensure_dir(ROOT / "outputs" / "latest")

    result = discover_manifold_catalog(
        config=config,
        seeds=seeds,
        shortlist_path=curated_dir / "manifold_shortlist.json",
        overrides_path=curated_dir / "manifold_overrides.json",
        raw_dir=raw_dir,
        refresh=args.refresh,
    )

    write_csv(processed_dir / "manifold_market_catalog.csv", result["catalog_rows"])
    write_json(processed_dir / "manifold_market_catalog.json", result["catalog_rows"])
    write_csv(output_dir / "selection_audit.csv", result["selection_audit_rows"])
    write_json(output_dir / "catalog_summary.json", result["summary"])

    print("Completed Manifold discovery catalog build.")
    print(f"Catalog candidates: {len(result['catalog_rows'])}")
    print(f"Approved: {result['summary']['approved_count']}")
    print(f"Pending: {result['summary']['pending_count']}")
    print(f"Rejected: {result['summary']['rejected_count']}")
    print(f"Outputs written to: {processed_dir} and {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
