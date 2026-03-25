from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.api_service import build_live_signal_artifacts  # noqa: E402
from cassandra_risk.promotion_store import apply_promotion_decision, latest_decisions_map, load_signal_registry  # noqa: E402
from cassandra_risk.promotion_workflow import build_promotion_queue  # noqa: E402


def _print_candidate(candidate: dict) -> None:
    print(candidate["contract_id"])
    print(f'  "{candidate["question_text"]}"')
    print(
        f"  Theme: {candidate['structural_theme']} | Volume: ${float(candidate.get('total_volume_usd') or 0.0):,.0f} | "
        f"Resolves: {candidate.get('resolution_date') or 'n/a'} | P_current: {float(candidate.get('current_probability') or 0.0):.3f}"
    )
    print(
        f"  Gates: {candidate['gates_passed']}/7 | Quality: {candidate['quality_score']:.3f} | "
        f"Auto: {candidate['auto_recommendation']}"
    )
    failures = []
    for key in (
        "gate1_probability_history",
        "gate2_resolution_horizon",
        "gate3_category_assigned",
        "gate4_volume_floor",
        "gate5_binary",
        "gate6_macro_relevant",
        "gate7_no_lookahead",
    ):
        if not candidate.get(key):
            failures.append(key.replace("_", " "))
    if failures:
        print(f"  Gate failed: {', '.join(failures)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Interactive promotion review queue for Cassandra live signal candidates.")
    parser.add_argument("--theme", default="")
    parser.add_argument("--min-gates", type=int, default=0)
    parser.add_argument("--include-rejected", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)

    if args.refresh:
        build_live_signal_artifacts(ROOT, refresh=True)

    load_signal_registry(ROOT)
    queue = build_promotion_queue(
        ROOT,
        theme=args.theme,
        min_gates=args.min_gates,
        include_rejected=args.include_rejected,
        decisions_map=latest_decisions_map(ROOT),
    )
    if args.limit > 0:
        queue = queue[: args.limit]

    print("PROMOTION REVIEW QUEUE")
    print("=" * 40)
    if not queue:
        print("No candidates match the current filters.")
        return 0

    for candidate in queue:
        _print_candidate(candidate)
        decision = input("  > Decision [A]pprove / [R]eject / [S]kip: ").strip().lower()
        if decision not in {"a", "r"}:
            print("  - skipped")
            print()
            continue
        reason = input("  > Reason: ").strip()
        if decision == "a":
            proxy_family_id = input(f"  > Proxy family id [{candidate['proxy_family_id']}]: ").strip() or candidate["proxy_family_id"]
            audit_row = apply_promotion_decision(
                ROOT,
                candidate=candidate,
                decision="APPROVED",
                reason=reason,
                decided_by="cli",
                proxy_family_id=proxy_family_id,
                aggregation_policy="max",
            )
            build_live_signal_artifacts(ROOT, refresh=False)
            print(f"  ✓ approved as {audit_row['event_family_id']}")
        else:
            audit_row = apply_promotion_decision(
                ROOT,
                candidate=candidate,
                decision="REJECTED",
                reason=reason,
                decided_by="cli",
                proxy_family_id=candidate["proxy_family_id"],
                aggregation_policy="max",
            )
            print(f"  ✗ rejected ({audit_row['decision_reason']})")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
