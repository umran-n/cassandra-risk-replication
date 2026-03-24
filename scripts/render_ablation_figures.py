from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.ablation_figures import render_ablation_figures  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--summary",
        default=str(ROOT / "outputs" / "ablation" / "ablation_summary.csv"),
        help="Path to ablation_summary.csv",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "outputs" / "ablation"),
        help="Directory to write figure PNGs into",
    )
    args = parser.parse_args()

    summary_path = Path(args.summary)
    output_dir = Path(args.output_dir)
    render_ablation_figures(summary_path, output_dir)
    print(f"Rendered ablation figures to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
