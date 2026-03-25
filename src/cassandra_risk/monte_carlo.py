from __future__ import annotations

import math
import random
from pathlib import Path

from .ablation_figures import BLACK, BLUE, GOLD, GREEN, LIGHT_GRID, RED, SLATE, WHITE, Canvas
from .backtest import summarize_strategy
from .utils import mean, percentile


def block_bootstrap_indices(observation_count: int, block_length: int, rng: random.Random) -> list[int]:
    if observation_count <= 0:
        return []
    if block_length <= 0:
        raise ValueError("block_length must be positive")

    indices: list[int] = []
    max_start = max(0, observation_count - 1)
    while len(indices) < observation_count:
        start = rng.randint(0, max_start)
        block_end = min(start + block_length, observation_count)
        indices.extend(range(start, block_end))
    return indices[:observation_count]


def bootstrap_metric_samples(
    returns: list[float],
    risk_free_annual_rates: list[float],
    *,
    block_length: int,
    samples: int,
    seed: int,
) -> dict[str, list[float]]:
    if len(returns) != len(risk_free_annual_rates):
        raise ValueError("returns and risk_free_annual_rates must have the same length")
    if len(returns) < 2:
        raise ValueError("returns series must contain at least two observations")

    rng = random.Random(seed)
    observation_count = len(returns) - 1
    metrics = {
        "sortino": [],
        "cagr": [],
        "mdd": [],
        "downside_deviation": [],
    }

    for _ in range(samples):
        sampled_indices = block_bootstrap_indices(observation_count, block_length, rng)
        sampled_returns = [0.0] + [returns[idx + 1] for idx in sampled_indices]
        sampled_risk_free = [risk_free_annual_rates[0]] + [risk_free_annual_rates[idx + 1] for idx in sampled_indices]

        equity = [1.0]
        for value in sampled_returns[1:]:
            equity.append(equity[-1] * (1.0 + value))

        summary = summarize_strategy(
            {
                "daily_returns": sampled_returns,
                "equity": equity,
                "positions": [1.0] * len(sampled_returns),
            },
            sampled_risk_free,
        )
        metrics["sortino"].append(summary["sortino"])
        metrics["cagr"].append(summary["cagr"])
        metrics["mdd"].append(summary["max_drawdown_daily"])
        metrics["downside_deviation"].append(summary["downside_deviation"])

    return metrics


def monte_carlo_summary_rows(
    observed: dict[str, float],
    samples: dict[str, list[float]],
) -> list[dict]:
    rows: list[dict] = []
    for metric in ("sortino", "cagr", "mdd", "downside_deviation"):
        values = sorted(samples[metric])
        observed_value = float(observed[metric])
        p_value = ""
        if metric == "sortino":
            p_value = sum(1 for value in samples["sortino"] if value > observed_value) / len(samples["sortino"])
        rows.append(
            {
                "metric": metric,
                "observed": observed_value,
                "mean_boot": mean(samples[metric]),
                "ci_lower_95": percentile(values, 0.025),
                "ci_upper_95": percentile(values, 0.975),
                "p_value": p_value,
            }
        )
    return rows


def render_sortino_distribution(
    path: Path,
    sortino_samples: list[float],
    *,
    observed: float,
    ci_lower: float,
    ci_upper: float,
    p_value: float,
) -> None:
    width = 1200
    height = 720
    canvas = Canvas(width, height, WHITE)

    margin_left = 90
    margin_right = 70
    margin_top = 90
    margin_bottom = 120
    chart_left = margin_left
    chart_right = width - margin_right
    chart_top = margin_top
    chart_bottom = height - margin_bottom
    chart_width = chart_right - chart_left
    chart_height = chart_bottom - chart_top

    samples = list(sortino_samples)
    x_min = min(samples + [observed])
    x_max = max(samples + [observed])
    if math.isclose(x_min, x_max):
        x_min -= 0.1
        x_max += 0.1

    bin_count = 18
    bin_width = (x_max - x_min) / bin_count
    counts = [0] * bin_count
    for value in samples:
        position = int((value - x_min) / bin_width) if bin_width > 0 else 0
        position = max(0, min(bin_count - 1, position))
        counts[position] += 1
    max_count = max(counts) if counts else 1

    canvas.draw_text(width // 2, 28, "MONTE CARLO SORTINO DISTRIBUTION", color=BLACK, scale=3, align="center")
    canvas.draw_text(
        width // 2,
        58,
        "V5_BECKER_TOP5_CAP_GEO | 500 BLOCK-BOOTSTRAP REPLICATES | BLOCK=20",
        color=SLATE,
        scale=2,
        align="center",
    )

    for tick in range(6):
        fraction = tick / 5
        y = chart_bottom - int(chart_height * fraction)
        canvas.line(chart_left, y, chart_right, y, LIGHT_GRID, thickness=1)
        label = f"{int(round(max_count * fraction))}"
        canvas.draw_text(chart_left - 12, y - 7, label, color=SLATE, scale=2, align="right")

    for idx, count in enumerate(counts):
        x0 = chart_left + int(chart_width * idx / bin_count)
        x1 = chart_left + int(chart_width * (idx + 1) / bin_count) - 4
        bar_height = 0 if max_count == 0 else int(chart_height * (count / max_count))
        canvas.fill_rect(x0 + 3, chart_bottom - bar_height, max(8, x1 - x0), bar_height, BLUE)

    canvas.line(chart_left, chart_bottom, chart_right, chart_bottom, BLACK, thickness=2)
    canvas.line(chart_left, chart_top, chart_left, chart_bottom, BLACK, thickness=2)

    def x_for_value(value: float) -> int:
        fraction = 0.0 if x_max == x_min else (value - x_min) / (x_max - x_min)
        return chart_left + int(chart_width * fraction)

    observed_x = x_for_value(observed)
    ci_lower_x = x_for_value(ci_lower)
    ci_upper_x = x_for_value(ci_upper)

    canvas.line(observed_x, chart_top, observed_x, chart_bottom, RED, thickness=3)
    canvas.line(ci_lower_x, chart_top + 20, ci_lower_x, chart_bottom, GOLD, thickness=2)
    canvas.line(ci_upper_x, chart_top + 20, ci_upper_x, chart_bottom, GOLD, thickness=2)

    for idx in range(6):
        fraction = idx / 5
        value = x_min + (x_max - x_min) * fraction
        x = chart_left + int(chart_width * fraction)
        canvas.line(x, chart_bottom, x, chart_bottom + 6, BLACK, thickness=1)
        canvas.draw_text(x, chart_bottom + 18, f"{value:.2f}", color=SLATE, scale=2, align="center")

    canvas.draw_text(chart_left, height - 68, f"OBSERVED SORTINO {observed:.3f}", color=RED, scale=2)
    canvas.draw_text(chart_left, height - 44, f"95% CI {ci_lower:.3f} TO {ci_upper:.3f}", color=GOLD, scale=2)
    canvas.draw_text(chart_left, height - 20, f"P(SORTINO > OBSERVED) = {p_value:.3f}", color=GREEN, scale=2)

    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save_png(path)
