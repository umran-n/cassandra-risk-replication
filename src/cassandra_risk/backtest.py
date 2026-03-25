from __future__ import annotations

import math
import random
from collections import defaultdict

from .utils import clamp, mean, parse_date, percentile, stddev


TRADING_DAYS = 252


def compute_price_returns(price_rows: list[dict]) -> tuple[list[str], list[float], list[float]]:
    dates = [row["date"] for row in price_rows]
    closes = [float(row["adjclose"]) for row in price_rows]
    returns = [0.0]
    for idx in range(1, len(closes)):
        returns.append((closes[idx] / closes[idx - 1]) - 1.0)
    return dates, closes, returns


def rolling_annualized_vol(returns: list[float], lookback: int) -> list[float]:
    values: list[float] = []
    for idx in range(len(returns)):
        if idx < lookback:
            values.append(0.0)
            continue
        window = returns[idx - lookback + 1 : idx + 1]
        values.append(stddev(window) * math.sqrt(TRADING_DAYS))
    return values


def compute_buy_hold_positions(dates: list[str]) -> list[float]:
    return [1.0 for _ in dates]


def compute_vol_target_positions(config: dict, returns: list[float]) -> list[float]:
    lookback = int(config["vol_target"]["lookback_days"])
    target = float(config["vol_target"]["target_vol"])
    max_position = float(config["vol_target"]["max_position"])
    rolling = rolling_annualized_vol(returns, lookback)
    positions: list[float] = []
    for vol in rolling:
        if vol <= 0:
            positions.append(max_position)
        else:
            positions.append(clamp(target / vol, 0.0, max_position))
    return positions


def compute_cassandra_signal(
    dates: list[str],
    daily_events: dict[str, dict[str, dict]],
    config: dict,
    lambda_scale: float = 1.0,
    probability_scale: float = 1.0,
) -> tuple[list[float], list[float], list[dict]]:
    thresholds = list(config["cassandra"]["rebalancing_thresholds"])
    rsi_values: list[float] = []
    hazard_values: list[float] = []
    threshold_events: list[dict] = []
    previous_rsi: float | None = None

    for day_string in dates:
        hazard = 0.0
        event_rows = daily_events.get(day_string, {})
        for row in event_rows.values():
            hazard += hazard_components_for_row(
                row,
                day_string,
                config,
                lambda_scale=lambda_scale,
                probability_scale=probability_scale,
            )["hazard_contribution"]
        rsi = 1.0 / (1.0 + hazard)
        rsi_values.append(rsi)
        hazard_values.append(hazard)
        if previous_rsi is not None:
            for threshold in thresholds:
                crossed_down = previous_rsi > threshold >= rsi
                crossed_up = previous_rsi < threshold <= rsi
                if crossed_down or crossed_up:
                    threshold_events.append(
                        {
                            "date": day_string,
                            "threshold": threshold,
                            "direction": "down" if crossed_down else "up",
                            "rsi": round(rsi, 6),
                            "hazard": round(hazard, 6)
                        }
                    )
        previous_rsi = rsi
    return rsi_values, hazard_values, threshold_events


def hazard_components_for_row(
    row: dict,
    day_string: str,
    config: dict,
    lambda_scale: float = 1.0,
    probability_scale: float = 1.0,
) -> dict:
    weights = config["cassandra"]["category_weights"]
    lambdas = config["cassandra"]["category_lambdas"]
    horizon_normalizer = float(config["cassandra"]["horizon_normalizer_days"])
    max_weight = max(float(value) for value in weights.values() if float(value) > 0.0)

    category = row["category"]
    weight = float(weights.get(category, 0.0))
    severity = 0.0 if max_weight <= 0 else weight / max_weight
    probability = clamp(float(row["probability"]) * probability_scale, 0.0, 1.0)
    current_date = parse_date(day_string)
    resolution_date = parse_date(row["resolution_date"])
    days_to_resolution = max((resolution_date - current_date).days, 1)
    horizon_units = days_to_resolution / horizon_normalizer
    decay_rate = float(lambdas.get(category, 0.1)) * lambda_scale

    # Split the original decay term into a short-horizon urgency term and a tail persistence term.
    velocity = math.exp(-decay_rate * min(horizon_units, 1.0))
    persistence = math.exp(-decay_rate * max(horizon_units - 1.0, 0.0))
    decay = velocity * persistence
    hazard = max_weight * probability * severity * velocity * persistence

    return {
        "category_weight": weight,
        "severity_scale_weight": max_weight,
        "probability_factor": probability,
        "severity_factor": severity,
        "velocity_factor": velocity,
        "persistence_factor": persistence,
        "decay_factor": decay,
        "days_to_resolution": days_to_resolution,
        "horizon_units": horizon_units,
        "decay_rate": decay_rate,
        "hazard_contribution": hazard,
    }


def build_hazard_attribution(
    dates: list[str],
    daily_events: dict[str, dict[str, dict]],
    config: dict,
    lambda_scale: float = 1.0,
    probability_scale: float = 1.0,
) -> tuple[list[dict], list[dict]]:
    attribution_rows: list[dict] = []
    decomposition_rows: list[dict] = []

    for day_string in dates:
        event_rows = daily_events.get(day_string, {})
        category_totals: dict[str, float] = defaultdict(float)
        theme_totals: dict[str, float] = defaultdict(float)
        day_rows: list[dict] = []

        for event_id, row in event_rows.items():
            components = hazard_components_for_row(
                row,
                day_string,
                config,
                lambda_scale=lambda_scale,
                probability_scale=probability_scale,
            )
            factor_sum = sum(
                (
                    components["probability_factor"],
                    components["severity_factor"],
                    components["velocity_factor"],
                    components["persistence_factor"],
                )
            )
            factor_sum = factor_sum if factor_sum > 0 else 1.0

            probability_hazard = components["hazard_contribution"] * components["probability_factor"] / factor_sum
            severity_hazard = components["hazard_contribution"] * components["severity_factor"] / factor_sum
            velocity_hazard = components["hazard_contribution"] * components["velocity_factor"] / factor_sum
            persistence_hazard = components["hazard_contribution"] * components["persistence_factor"] / factor_sum

            category_totals[row["category"]] += components["hazard_contribution"]
            theme_totals[row.get("structural_theme", "")] += components["hazard_contribution"]
            day_rows.append(
                {
                    "date": day_string,
                    "event_id": event_id,
                    "category": row["category"],
                    "structural_theme": row.get("structural_theme", ""),
                    "question": row["question"],
                    "event_probability": float(row["probability"]),
                    "hazard_contribution": components["hazard_contribution"],
                    "probability_factor": components["probability_factor"],
                    "severity_factor": components["severity_factor"],
                    "velocity_factor": components["velocity_factor"],
                    "persistence_factor": components["persistence_factor"],
                    "probability_component_hazard": probability_hazard,
                    "severity_component_hazard": severity_hazard,
                    "velocity_component_hazard": velocity_hazard,
                    "persistence_component_hazard": persistence_hazard,
                    "category_weight": components["category_weight"],
                    "severity_scale_weight": components["severity_scale_weight"],
                    "days_to_resolution": components["days_to_resolution"],
                    "horizon_units": components["horizon_units"],
                    "decay_rate": components["decay_rate"],
                    "decay_factor": components["decay_factor"],
                    "proxy_family_id": row.get("proxy_family_id"),
                    "proxy_relation": row.get("proxy_relation"),
                    "aggregation_policy": row.get("aggregation_policy"),
                    "family_aggregation_policy": row.get("family_aggregation_policy"),
                    "event_aggregation_policy": row.get("event_aggregation_policy"),
                    "event_window_start": row.get("event_window_start"),
                    "event_window_end": row.get("event_window_end"),
                    "quality_score": row.get("quality_score"),
                    "proxy_family_count": row.get("proxy_family_count", 1),
                    "family_proxy_count": row.get("family_proxy_count", 1),
                    "dominant_family_market_id": row.get("dominant_family_market_id"),
                    "dominant_family_question": row.get("dominant_family_question"),
                    "dominant_family_probability": row.get("dominant_family_probability"),
                    "dominant_event_market_id": row.get("dominant_event_market_id"),
                    "dominant_event_question": row.get("dominant_event_question"),
                    "dominant_event_probability": row.get("dominant_event_probability"),
                }
            )

        total_hazard = sum(row["hazard_contribution"] for row in day_rows)
        rsi = 1.0 / (1.0 + total_hazard)
        rsi_drag = 1.0 - rsi
        ranked = sorted(day_rows, key=lambda item: item["hazard_contribution"], reverse=True)
        dominant_event_id = ranked[0]["event_id"] if ranked else ""
        dominant_category = max(category_totals, key=category_totals.get) if category_totals else ""
        dominant_theme = max(theme_totals, key=theme_totals.get) if theme_totals else ""

        probability_total = sum(row["probability_component_hazard"] for row in day_rows)
        severity_total = sum(row["severity_component_hazard"] for row in day_rows)
        velocity_total = sum(row["velocity_component_hazard"] for row in day_rows)
        persistence_total = sum(row["persistence_component_hazard"] for row in day_rows)

        for rank, row in enumerate(ranked, start=1):
            row["total_hazard"] = total_hazard
            row["rsi"] = rsi
            row["rsi_drag"] = rsi_drag
            row["event_rank_by_hazard"] = rank
            row["event_hazard_share"] = 0.0 if total_hazard == 0 else row["hazard_contribution"] / total_hazard
            row["category_hazard_share"] = 0.0 if total_hazard == 0 else category_totals[row["category"]] / total_hazard
            row["theme_hazard_share"] = 0.0 if total_hazard == 0 else theme_totals[row["structural_theme"]] / total_hazard
            row["dominant_event_flag"] = rank == 1
            row["dominant_category_flag"] = row["category"] == dominant_category
            row["dominant_theme_flag"] = row["structural_theme"] == dominant_theme
            attribution_rows.append(row)

        probability_share = 0.0 if total_hazard == 0 else probability_total / total_hazard
        severity_share = 0.0 if total_hazard == 0 else severity_total / total_hazard
        velocity_share = 0.0 if total_hazard == 0 else velocity_total / total_hazard
        persistence_share = 0.0 if total_hazard == 0 else persistence_total / total_hazard

        decomposition_rows.append(
            {
                "date": day_string,
                "total_hazard": total_hazard,
                "rsi": rsi,
                "rsi_drag": rsi_drag,
                "active_event_count": len(day_rows),
                "dominant_event_id": dominant_event_id,
                "dominant_category": dominant_category,
                "dominant_theme": dominant_theme,
                "probability_component_hazard": probability_total,
                "severity_component_hazard": severity_total,
                "velocity_component_hazard": velocity_total,
                "persistence_component_hazard": persistence_total,
                "probability_share_of_hazard": probability_share,
                "severity_share_of_hazard": severity_share,
                "velocity_share_of_hazard": velocity_share,
                "persistence_share_of_hazard": persistence_share,
                "probability_rsi_drag": rsi_drag * probability_share,
                "severity_rsi_drag": rsi_drag * severity_share,
                "velocity_rsi_drag": rsi_drag * velocity_share,
                "persistence_rsi_drag": rsi_drag * persistence_share,
            }
        )

    return attribution_rows, decomposition_rows


def simulate_strategy(dates: list[str], returns: list[float], positions: list[float], transaction_cost_bps: float) -> dict:
    if not (len(dates) == len(returns) == len(positions)):
        raise ValueError("dates, returns, and positions must have equal length")
    costs = transaction_cost_bps / 10000.0
    equity = [1.0]
    strategy_returns = [0.0]
    previous_position = positions[0]
    for idx in range(1, len(dates)):
        signal_position = positions[idx - 1]
        trade_cost = abs(signal_position - previous_position) * costs
        realized = signal_position * returns[idx] - trade_cost
        strategy_returns.append(realized)
        equity.append(equity[-1] * (1.0 + realized))
        previous_position = signal_position
    return {
        "dates": dates,
        "positions": positions,
        "daily_returns": strategy_returns,
        "equity": equity
    }


def max_drawdown(equity: list[float]) -> float:
    peak = equity[0]
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        drawdown = (value / peak) - 1.0
        worst = min(worst, drawdown)
    return worst


def annual_to_daily_rate(annual_rate: float) -> float:
    return (1.0 + annual_rate) ** (1.0 / TRADING_DAYS) - 1.0


def monthly_resampled_equity(dates: list[str], equity: list[float]) -> list[float]:
    by_month: dict[str, float] = {}
    ordered_months: list[str] = []
    for day, value in zip(dates, equity):
        month_key = day[:7]
        if month_key not in by_month:
            ordered_months.append(month_key)
        by_month[month_key] = value
    return [by_month[month_key] for month_key in ordered_months]


def monthly_drawdown_episodes(dates: list[str], equity: list[float]) -> list[float]:
    grouped: dict[str, list[float]] = {}
    ordered_months: list[str] = []
    for day, value in zip(dates, equity):
        month_key = day[:7]
        if month_key not in grouped:
            grouped[month_key] = []
            ordered_months.append(month_key)
        grouped[month_key].append(value)
    return [max_drawdown(grouped[month_key]) for month_key in ordered_months]


def monthly_drawdown_episode_stats(dates: list[str], equity: list[float]) -> dict:
    episodes = monthly_drawdown_episodes(dates, equity)
    return {
        "monthly_mdd_mean": mean(episodes),
        "monthly_mdd_worst": min(episodes) if episodes else 0.0,
        "monthly_mdd_episode_count": len(episodes),
    }


def downside_deviation(returns: list[float], target_returns: list[float] | None = None) -> float:
    if target_returns is None:
        target_returns = [0.0] * len(returns)
    downside = [min(value - target_returns[idx], 0.0) for idx, value in enumerate(returns[1:], start=1)]
    if not downside:
        return 0.0
    squared = sum(value * value for value in downside) / len(downside)
    return math.sqrt(squared) * math.sqrt(TRADING_DAYS)


def cvar_95(returns: list[float]) -> float:
    observations = sorted(returns[1:])
    if not observations:
        return 0.0
    cutoff = max(1, int(math.ceil(0.05 * len(observations))))
    tail = observations[:cutoff]
    return mean(tail)


def count_cash_days(positions: list[float], threshold: float = 0.1) -> tuple[int, int]:
    total = 0
    longest = 0
    current = 0
    for position in positions:
        if position <= threshold:
            total += 1
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return total, longest


def summarize_strategy(result: dict, risk_free_annual_rates: list[float] | None = None) -> dict:
    returns = result["daily_returns"]
    equity = result["equity"]
    positions = result["positions"]
    dates = result.get("dates")
    total_return = equity[-1] - 1.0
    periods = max(len(returns) - 1, 1)
    cagr = equity[-1] ** (TRADING_DAYS / periods) - 1.0
    vol = stddev(returns[1:]) * math.sqrt(TRADING_DAYS)
    avg_daily = mean(returns[1:])
    sharpe = 0.0 if vol == 0 else (avg_daily * TRADING_DAYS) / vol
    if risk_free_annual_rates is None:
        risk_free_annual_rates = [0.0] * len(returns)
    risk_free_daily_rates = [annual_to_daily_rate(value) for value in risk_free_annual_rates]
    avg_excess_daily = mean(
        [returns[idx] - risk_free_daily_rates[idx] for idx in range(1, len(returns))]
    )
    dd = downside_deviation(returns, risk_free_daily_rates)
    sortino = 0.0 if dd == 0 else (avg_excess_daily * TRADING_DAYS) / dd
    mdd_daily = max_drawdown(equity)
    mdd_monthly = mdd_daily if dates is None else max_drawdown(monthly_resampled_equity(dates, equity))
    calmar = 0.0 if mdd_daily == 0 else cagr / abs(mdd_daily)
    cash_days, longest_cash = count_cash_days(positions)
    return {
        "cagr": cagr,
        "total_return": total_return,
        "volatility": vol,
        "max_drawdown": mdd_daily,
        "max_drawdown_daily": mdd_daily,
        "max_drawdown_monthly": mdd_monthly,
        "downside_deviation": dd,
        "cvar_95": cvar_95(returns),
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "avg_position": mean(positions),
        "days_in_90pct_cash": cash_days,
        "max_consecutive_cash_days": longest_cash
    }


def metrics_table(results: dict[str, dict]) -> list[dict]:
    rows = []
    metric_order = [
        "cagr",
        "total_return",
        "volatility",
        "max_drawdown_daily",
        "max_drawdown_monthly",
        "downside_deviation",
        "cvar_95",
        "sharpe",
        "sortino",
        "calmar",
        "avg_position",
        "days_in_90pct_cash",
        "max_consecutive_cash_days"
    ]
    for metric in metric_order:
        row = {"metric": metric}
        for strategy, summary in results.items():
            row[strategy] = summary[metric]
        rows.append(row)
    return rows


def compare_to_paper(results: dict[str, dict], paper_metrics: dict) -> list[dict]:
    rows = []
    mapping = {
        "buy_hold": "buy_and_hold",
        "vol_target": "vol_target",
        "cassandra": "cassandra"
    }
    for strategy, paper_key in mapping.items():
        for metric, value in results[strategy].items():
            if metric == "max_drawdown":
                continue
            if metric == "max_drawdown_daily":
                paper_value = None
            elif metric == "max_drawdown_monthly":
                paper_value = paper_metrics[paper_key].get("max_drawdown")
            elif metric not in paper_metrics[paper_key]:
                continue
            else:
                paper_value = paper_metrics[paper_key][metric]
            rows.append(
                {
                    "strategy": strategy,
                    "metric": metric,
                    "reconstructed": value,
                    "paper": paper_value,
                    "delta": None if paper_value is None else value - paper_value
                }
            )
    return rows


def bootstrap_confidence_intervals(
    strategy_returns: dict[str, list[float]],
    block_size: int,
    resamples: int,
    seed: int,
    risk_free_annual_rates: list[float] | None = None
) -> list[dict]:
    rng = random.Random(seed)
    strategy_names = list(strategy_returns.keys())
    observations = len(next(iter(strategy_returns.values())))
    metrics: dict[str, dict[str, list[float]]] = {
        strategy: defaultdict(list) for strategy in strategy_names
    }

    for _ in range(resamples):
        sample_indices: list[int] = []
        while len(sample_indices) < observations:
            block_start = rng.randint(1, max(1, observations - block_size))
            sample_indices.extend(range(block_start, min(block_start + block_size, observations)))
        sample_indices = sample_indices[:observations]
        sampled_risk_free = None
        if risk_free_annual_rates is not None:
            sampled_risk_free = [risk_free_annual_rates[0]] + [
                risk_free_annual_rates[idx] for idx in sample_indices[1:]
            ]
        for strategy in strategy_names:
            sampled = [0.0] + [strategy_returns[strategy][idx] for idx in sample_indices[1:]]
            equity = [1.0]
            for value in sampled[1:]:
                equity.append(equity[-1] * (1.0 + value))
            summary = summarize_strategy(
                {
                    "daily_returns": sampled,
                    "equity": equity,
                    "positions": [1.0] * len(sampled)
                },
                sampled_risk_free,
            )
            for metric in ("cagr", "max_drawdown", "sharpe", "sortino", "cvar_95"):
                metrics[strategy][metric].append(summary[metric])

    rows = []
    for strategy in strategy_names:
        for metric, values in metrics[strategy].items():
            sorted_values = sorted(values)
            rows.append(
                {
                    "strategy": strategy,
                    "metric": metric,
                    "ci_low": percentile(sorted_values, 0.025),
                    "ci_high": percentile(sorted_values, 0.975)
                }
            )
    return rows


def event_window_analysis(
    seeds: list[dict],
    price_dates: list[str],
    price_returns: list[float],
    cassandra_positions: list[float],
    cassandra_rsi: list[float],
    daily_events: dict[str, dict[str, dict]]
) -> list[dict]:
    date_to_index = {day: idx for idx, day in enumerate(price_dates)}
    rows = []
    for seed in seeds:
        if seed["analysis_bucket"] not in {"drawdown", "false_positive"}:
            continue
        event_date = seed["event_date"]
        if event_date not in date_to_index:
            continue
        idx = date_to_index[event_date]
        active_probabilities = []
        active_rsi = []
        window_start = max(0, idx - 5)
        window_end = min(len(price_dates) - 1, idx + 5)
        for pos in range(window_start, window_end + 1):
            day = price_dates[pos]
            event_row = daily_events.get(day, {}).get(seed["event_id"])
            if event_row:
                active_probabilities.append(float(event_row["probability"]))
                active_rsi.append(cassandra_rsi[pos])
        peak_prob = max(active_probabilities) if active_probabilities else 0.0
        rsi_low = min(active_rsi) if active_rsi else 1.0
        hold_curve = 1.0
        cass_curve = 1.0
        for forward in range(idx + 1, min(idx + 6, len(price_returns))):
            hold_curve *= 1.0 + price_returns[forward]
            cass_curve *= 1.0 + cassandra_positions[forward - 1] * price_returns[forward]
        buy_hold_drawdown = hold_curve - 1.0
        cassandra_realized = cass_curve - 1.0
        rows.append(
            {
                "event_id": seed["event_id"],
                "event_date": event_date,
                "category": seed["category"],
                "analysis_bucket": seed["analysis_bucket"],
                "peak_probability": peak_prob,
                "rsi_low": rsi_low,
                "position_cut": -(1.0 - rsi_low),
                "spy_5d_drawdown": buy_hold_drawdown,
                "cassandra_avoided": buy_hold_drawdown - cassandra_realized
            }
        )
    return rows


def brier_score_summary(rows: list[dict]) -> list[dict]:
    by_event: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_event[row["event_id"]].append(row)

    event_scores = []
    source_scores: dict[str, list[float]] = defaultdict(list)
    aggregated_scores: list[float] = []
    for event_id, event_rows in by_event.items():
        ordered = sorted(event_rows, key=lambda row: row["date"])
        final_probability = float(ordered[-1]["probability"])
        outcome = 1.0 if ordered[-1]["resolved_outcome"] == "YES" else 0.0
        score = (final_probability - outcome) ** 2
        aggregated_scores.append(score)
        source_scores[ordered[-1]["source"]].append(score)
        event_scores.append(
            {
                "event_id": event_id,
                "source": ordered[-1]["source"],
                "resolved_outcome": ordered[-1]["resolved_outcome"],
                "final_probability": final_probability,
                "brier_score": score
            }
        )

    summary = [
        {
            "forecast_source": "naive_50_50",
            "mean_brier_score": 0.25,
            "sample_size": len(event_scores)
        },
        {
            "forecast_source": "cassandra_aggregated",
            "mean_brier_score": mean(aggregated_scores),
            "sample_size": len(event_scores)
        }
    ]
    for source, scores in sorted(source_scores.items()):
        summary.append(
            {
                "forecast_source": source.lower(),
                "mean_brier_score": mean(scores),
                "sample_size": len(scores)
            }
        )
    return summary
