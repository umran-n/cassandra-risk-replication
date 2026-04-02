from __future__ import annotations

from pathlib import Path

from .utils import ensure_dir


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _num(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def render_report(
    path: Path,
    summary: dict,
    gap_rows: list[dict],
    model_rows: list[dict],
    oos_rows: list[dict],
    coherence_rows: list[dict],
    entanglement_rows: list[dict],
    contagion_rows: list[dict],
    tail_screen_rows: list[dict],
) -> None:
    ensure_dir(path.parent)
    target_count = sum(int(row["target_count"]) for row in gap_rows)
    achieved_count = sum(int(row["achieved_count"]) for row in gap_rows)
    lines: list[str] = []
    lines.append("# Quantum Capital Allocation closest-public replication")
    lines.append("")
    lines.append('> data_tier="public_proxy"')
    lines.append("")
    lines.append("## Sample coverage")
    lines.append("")
    lines.append(
        f"Target window: `{summary['target_start']}` to `{summary['target_end']}`. "
        f"Target events: `{target_count}`. Achieved ledger rows: `{achieved_count}`. "
        f"Primary-regression eligible rows: `{summary['eligible_events']}`."
    )
    lines.append("")
    lines.append("| Ticker | Target | Achieved | Gap |")
    lines.append("| --- | ---: | ---: | ---: |")
    for row in gap_rows:
        lines.append(
            f"| {row['ticker']} | {int(row['target_count'])} | {int(row['achieved_count'])} | {int(row['gap'])} |"
        )
    lines.append("")
    lines.append("## Model summary")
    lines.append("")
    lines.append("| Model | R2 | N |")
    lines.append("| --- | ---: | ---: |")
    for row in model_rows:
        lines.append(f"| {row['model']} | {_num(row['r2'])} | {int(row['n_obs'])} |")
    lines.append("")
    lines.append("## Out-of-sample")
    lines.append("")
    lines.append("| Model | R2 | RMSE | MAE | Directional Accuracy |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for row in oos_rows:
        lines.append(
            f"| {row['model']} | {_num(row['r2'])} | {_num(row['rmse'])} | {_num(row['mae'])} | {_pct(row['directional_accuracy'])} |"
        )
    lines.append("")
    lines.append("## Coherence")
    lines.append("")
    lines.append("| Event | Ticker | Tau | Fit R2 | Qualified |")
    lines.append("| --- | --- | ---: | ---: | --- |")
    for row in coherence_rows[:15]:
        lines.append(
            f"| {row['event_id']} | {row['ticker']} | {_num(row['tau'])} | {_num(row['fit_r2'])} | {row['qualified']} |"
        )
    lines.append("")
    lines.append("## Entanglement")
    lines.append("")
    lines.append("| Ticker | Events | Entropy (bits) | d_eff | Tier |")
    lines.append("| --- | ---: | ---: | ---: | --- |")
    for row in entanglement_rows:
        lines.append(
            f"| {row['ticker']} | {int(row['event_count'])} | {_num(row['entropy_bits'])} | {_num(row['d_eff'])} | {row['risk_tier']} |"
        )
    lines.append("")
    lines.append("## Tail-risk screen")
    lines.append("")
    lines.append("| Event | Ticker | Drawdown 50D | d_eff | Tier | Screen Probability |")
    lines.append("| --- | --- | ---: | ---: | --- | ---: |")
    for row in tail_screen_rows[:15]:
        lines.append(
            f"| {row['event_id']} | {row['ticker']} | {_pct(row['post_event_drawdown_50d'])} | {_num(row['d_eff'])} | {row['risk_tier']} | {_pct(row['screen_probability'])} |"
        )
    lines.append("")
    lines.append("## Contagion edges")
    lines.append("")
    lines.append("| Left | Right | xi_ij | Observations |")
    lines.append("| --- | --- | ---: | ---: |")
    for row in contagion_rows[:15]:
        lines.append(
            f"| {row['left_ticker']} | {row['right_ticker']} | {_num(row['xi_ij'])} | {int(row['observations'])} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Management sentiment uses explicit public-proxy labeling and falls back to lexical scoring when FinBERT infrastructure is unavailable in the current environment.")
    lines.append("- Market and options sub-scores are public proxies by design unless a historical Yahoo consensus/options reconstruction succeeds for a given event.")
    lines.append("- If achieved counts remain below the paper target, the gap is surfaced directly rather than silently padded.")
    path.write_text("\n".join(lines), encoding="utf-8")
