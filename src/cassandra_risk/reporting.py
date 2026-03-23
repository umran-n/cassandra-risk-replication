from __future__ import annotations

from pathlib import Path

from .utils import ensure_dir


def as_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def as_num(value: float) -> str:
    return f"{value:.3f}"


def render_report(
    path: Path,
    metrics_rows: list[dict],
    comparison_rows: list[dict],
    robustness_rows: list[dict],
    bootstrap_rows: list[dict],
    brier_rows: list[dict],
    event_rows: list[dict],
    replication_gaps: list[str]
) -> None:
    ensure_dir(path.parent)
    lines: list[str] = []
    lines.append("# Cassandra-Risk closest-public replication")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("This run uses Yahoo Finance SPY prices, recovered Manifold market histories where possible, and paper-based manual reconstructions where the paper does not publish historical event-series data.")
    lines.append("")
    lines.append("## Portfolio metrics")
    lines.append("")
    lines.append("| Metric | Buy & Hold | Vol Target | Cassandra |")
    lines.append("| --- | ---: | ---: | ---: |")
    percentage_metrics = {
        "cagr",
        "total_return",
        "volatility",
        "max_drawdown_daily",
        "max_drawdown_monthly",
        "downside_deviation",
        "cvar_95",
        "avg_position"
    }
    for row in metrics_rows:
        metric = row["metric"]
        formatted = []
        for key in ("buy_hold", "vol_target", "cassandra"):
            value = row[key]
            if metric in percentage_metrics:
                formatted.append(as_pct(value))
            elif "days" in metric:
                formatted.append(str(int(round(value))))
            else:
                formatted.append(as_num(value))
        lines.append(f"| {metric} | {formatted[0]} | {formatted[1]} | {formatted[2]} |")
    lines.append("")
    lines.append("## Paper comparison")
    lines.append("")
    lines.append("| Strategy | Metric | Reconstructed | Paper | Delta |")
    lines.append("| --- | --- | ---: | ---: | ---: |")
    for row in comparison_rows:
        metric = row["metric"]
        reconstructed = row["reconstructed"]
        paper = row["paper"]
        delta = row["delta"]
        if paper is None:
            paper_rendered = "n/a"
            delta_rendered = "n/a"
        elif metric in percentage_metrics:
            paper_rendered = as_pct(paper)
            delta_rendered = as_pct(delta)
        elif "days" in metric:
            paper_rendered = str(int(round(paper)))
            delta_rendered = f"{delta:.1f}"
        else:
            paper_rendered = as_num(paper)
            delta_rendered = as_num(delta)
        if metric in percentage_metrics:
            lines.append(
                f"| {row['strategy']} | {metric} | {as_pct(reconstructed)} | {paper_rendered} | {delta_rendered} |"
            )
        elif "days" in metric:
            lines.append(
                f"| {row['strategy']} | {metric} | {int(round(reconstructed))} | {paper_rendered} | {delta_rendered} |"
            )
        else:
            lines.append(
                f"| {row['strategy']} | {metric} | {as_num(reconstructed)} | {paper_rendered} | {delta_rendered} |"
            )
    lines.append("")
    lines.append("## Robustness view")
    lines.append("")
    lines.append("| Scenario | CAGR | Max Drawdown | Sortino | Avg Position |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for row in robustness_rows:
        lines.append(
            f"| {row['scenario']} | {as_pct(row['cagr'])} | {as_pct(row['max_drawdown'])} | {as_num(row['sortino'])} | {as_pct(row['avg_position'])} |"
        )
    lines.append("")
    lines.append("## Bootstrap confidence intervals")
    lines.append("")
    lines.append("| Strategy | Metric | 95% CI Low | 95% CI High |")
    lines.append("| --- | --- | ---: | ---: |")
    for row in bootstrap_rows:
        metric = row["metric"]
        low = row["ci_low"]
        high = row["ci_high"]
        if metric in percentage_metrics:
            lines.append(f"| {row['strategy']} | {metric} | {as_pct(low)} | {as_pct(high)} |")
        else:
            lines.append(f"| {row['strategy']} | {metric} | {as_num(low)} | {as_num(high)} |")
    lines.append("")
    lines.append("## Brier score summary")
    lines.append("")
    lines.append("| Forecast source | Mean Brier score | Sample size |")
    lines.append("| --- | ---: | ---: |")
    for row in brier_rows:
        lines.append(
            f"| {row['forecast_source']} | {as_num(row['mean_brier_score'])} | {int(row['sample_size'])} |"
        )
    lines.append("")
    lines.append("## Event-by-event analysis")
    lines.append("")
    lines.append("| Event | Bucket | Peak Prob | RSI Low | Position Cut | SPY 5D Drawdown | Cassandra Avoided |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for row in event_rows:
        lines.append(
            f"| {row['event_id']} | {row['analysis_bucket']} | {as_pct(row['peak_probability'])} | {as_pct(row['rsi_low'])} | {as_pct(row['position_cut'])} | {as_pct(row['spy_5d_drawdown'])} | {as_pct(row['cassandra_avoided'])} |"
        )
    lines.append("")
    lines.append("## Replication gaps")
    lines.append("")
    for gap in replication_gaps:
        lines.append(f"- {gap}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
