from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.api_service import build_live_signal_artifacts  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    refresh = "--refresh" in argv

    payload = build_live_signal_artifacts(ROOT, refresh=refresh)
    snapshots = payload["snapshots"]
    rsi_snapshot = payload["rsi_snapshot"]

    print("Unified signal book built.")
    print(f"Selected signals: {len(snapshots)}")
    print(f"Current RSI: {rsi_snapshot['rsi']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
