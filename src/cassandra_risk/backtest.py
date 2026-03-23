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
    weights = config["cassandra"]["category_weights"]
    lambdas = config["cassandra"]["category_lambdas"]
    horizon_normalizer = float(config["cassandra"]["horizon_normalizer_days"])
    thresholds = list(config["cassandra"]["rebalancing_thresholds"])
    rsi_values: list[float] = []
    hazard_values: list[float] = []
    threshold_events: list[dict] = []
    previous_rsi: float | None = None

    for day_string in dates:
        hazard = 0.0
        event_rows = daily_events.get(day_string, {})
        current_date = parse_date(day_string)
        for row in event_rows.values():
            category = row["category"]
            probability = clamp(float(row["probability"]) * probability_scale, 0.0, 1.0)
            resolution_date = parse_date(row["resolution_date"])
            days_to_resolution = max((resolution_date - current_date).days, 1)
            decay_rate = float(lambdas.get(category, 0.1)) * lambda_scale
            decay = math.exp(-decay_rate * days_to_resolution / horizon_normalizer)
            hazard += float(weights.get(category, 0.0)) * decay * probability
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


def downside_deviation(returns: list[float]) -> float:
    downside = [min(value, 0.0) for value in returns[1:]]
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


def summarize_strategy(result: dict) -> dict:
    returns = result["daily_returns"]
    equity = result["equity"]
    positions = result["positions"]
    total_return = equity[-1] - 1.0
    periods = max(len(returns) - 1, 1)
    cagr = equity[-1] ** (TRADING_DAYS / periods) - 1.0
    vol = stddev(returns[1:]) * math.sqrt(TRADING_DAYS)
    avg_daily = mean(returns[1:])
    sharpe = 0.0 if vol == 0 else (avg_daily * TRADING_DAYS) / vol
    dd = downside_deviation(returns)
    sortino = 0.0 if dd == 0 else (avg_daily * TRADING_DAYS) / dd
    mdd = max_drawdown(equity)
    calmar = 0.0 if mdd == 0 else cagr / abs(mdd)
    cash_days, longest_cash = count_cash_days(positions)
    return {
        "cagr": cagr,
        "total_return": total_return,
        "volatility": vol,
        "max_drawdown": mdd,
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
        "max_drawdown",
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
            if metric not in paper_metrics[paper_key]:
                continue
            paper_value = paper_metrics[paper_key][metric]
            rows.append(
                {
                    "strategy": strategy,
                    "metric": metric,
                    "reconstructed": value,
                    "paper": paper_value,
                    "delta": value - paper_value
                }
            )
    return rows


def bootstrap_confidence_intervals(
    strategy_returns: dict[str, list[float]],
    block_size: int,
    resamples: int,
    seed: int
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
                }
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
