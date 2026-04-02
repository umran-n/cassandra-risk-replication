from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from qca_replication.pipeline import run_pipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "config" / "qca_config.json"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    result = run_pipeline(ROOT, Path(args.config), refresh=args.refresh)
    print("Completed QCA closest-public replication.")
    print(f"Outputs written to: {result['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
