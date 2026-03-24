from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.config import load_json  # noqa: E402
from cassandra_risk.polymarket import (  # noqa: E402
    build_fetch_summary_markdown,
    build_polymarket_candidates,
    write_fetch_errors,
    write_polymarket_candidates,
)
from cassandra_risk.utils import ensure_dir, write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Refresh cached Polymarket event and price-history data")
    args = parser.parse_args()

    config = load_json(ROOT / "config" / "backtest_config.json")
    raw_dir = ensure_dir(ROOT / "data" / "raw")
    candidates_dir = ensure_dir(ROOT / "data" / "candidates")

    candidates, summary, errors = build_polymarket_candidates(
        sample_start=config["sample"]["start"],
        sample_end=config["sample"]["end"],
        raw_dir=raw_dir,
        refresh=args.refresh,
    )

    output_path = candidates_dir / "polymarket_candidates.json"
    write_polymarket_candidates(output_path, candidates)
    write_json(candidates_dir / "polymarket_candidates_summary.json", summary)
    write_fetch_errors(candidates_dir / "fetch_errors.log", errors)
    (candidates_dir / "fetch_summary.md").write_text(
        build_fetch_summary_markdown(
            sample_start=config["sample"]["start"],
            sample_end=config["sample"]["end"],
            summary=summary,
            candidates=candidates,
            errors=errors,
        ),
        encoding="utf-8",
    )

    print("Completed Polymarket historical dredge.")
    print(f"Events scanned: {summary['event_count']}")
    print(f"Markets scanned: {summary['market_count']}")
    print(f"Category gate pass: {summary['non_noise_market_count']}")
    print(f"Horizon gate pass: {summary['time_gate_pass_count']}")
    print(f"Probability gate pass: {summary['probability_gate_pass_count']}")
    print(f"Eligible candidates written: {summary['eligible_count']}")
    print(f"Fetch errors logged: {len(errors)}")
    print(f"Output written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
