from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .clients import build_sec_document_url, fetch_sec_company_facts, fetch_sec_document, fetch_sec_submissions, fetch_yahoo_chart
from .discovery import expand_submission_rows, fetch_filing_text_bundle
from .utils import (
    annualize_volatility,
    clamp,
    closest_previous_date,
    correlation,
    extract_contextual_money,
    format_date,
    map_announcement_to_t0,
    mean,
    normalize_whitespace,
    parse_date,
    parse_datetime,
    safe_div,
    stddev,
    strip_html,
    tanh_score,
)


TRADING_DAYS = 252


def compute_theta(s_mgmt: float | None, s_market: float | None, s_options: float | None, h_t: float = 1.0) -> float | None:
    if s_mgmt is None or s_market is None or s_options is None:
        return None
    return clamp(180.0 * (1.0 - mean([s_mgmt, s_market, s_options])) * h_t, 0.0, 180.0)


def compute_qii(particle_amplitude: float | None, wave_amplitude: float | None, theta_degrees: float | None) -> float | None:
    if particle_amplitude is None or wave_amplitude is None or theta_degrees is None:
        return None
    denom = particle_amplitude ** 2 + wave_amplitude ** 2
    harmonic = 0.0 if denom == 0 else (2.0 * particle_amplitude * wave_amplitude) / denom
    return harmonic * math.cos(math.radians(theta_degrees))


def _fact_rows(company_facts: dict, taxonomy: str, tags: list[str]) -> tuple[list[dict], str | None]:
    facts = company_facts.get("facts", {}).get(taxonomy, {})
    for tag in tags:
        entry = facts.get(tag)
        if not entry:
            continue
        units = entry.get("units", {})
        if not units:
            continue
        unit_name = next(iter(units))
        return units[unit_name], tag
    return [], None


def _filter_available_rows(rows: list[dict], asof: date) -> list[dict]:
    filtered = []
    for row in rows:
        filed = row.get("filed")
        if filed and parse_date(filed) > asof:
            continue
        filtered.append(row)
    return filtered


def _latest_instant_value(rows: list[dict], asof: date) -> float | None:
    filtered = []
    for row in _filter_available_rows(rows, asof):
        end = row.get("end")
        if not end:
            continue
        end_date = parse_date(end)
        if end_date > asof:
            continue
        filtered.append((end_date, row.get("filed", "1900-01-01"), float(row["val"])))
    if not filtered:
        return None
    filtered.sort(key=lambda item: (item[0], item[1]))
    return filtered[-1][2]


def _dedupe_period_rows(rows: list[dict], asof: date, min_days: int, max_days: int) -> list[dict]:
    chosen: dict[str, dict] = {}
    for row in _filter_available_rows(rows, asof):
        start = row.get("start")
        end = row.get("end")
        if not start or not end:
            continue
        start_date = parse_date(start)
        end_date = parse_date(end)
        duration = (end_date - start_date).days + 1
        if end_date > asof or duration < min_days or duration > max_days:
            continue
        current = chosen.get(end)
        if current is None or row.get("filed", "") > current.get("filed", ""):
            chosen[end] = row
    return [chosen[key] for key in sorted(chosen)]


def _quarterly_flow_sum(rows: list[dict], asof: date, quarters: int = 4) -> float | None:
    quarter_rows = _dedupe_period_rows(rows, asof, 70, 110)
    if len(quarter_rows) < quarters:
        return None
    return sum(float(row["val"]) for row in quarter_rows[-quarters:])


def _latest_quarter_value(rows: list[dict], asof: date) -> float | None:
    quarter_rows = _dedupe_period_rows(rows, asof, 70, 110)
    if not quarter_rows:
        return None
    return float(quarter_rows[-1]["val"])


def _previous_quarter_values(rows: list[dict], asof: date, count: int = 4) -> list[float]:
    quarter_rows = _dedupe_period_rows(rows, asof, 70, 110)
    if len(quarter_rows) <= 1:
        return []
    values = [float(row["val"]) for row in quarter_rows[:-1]]
    return values[-count:]


def _close_lookup(chart_payload: dict) -> tuple[dict[date, float], list[date], dict[date, float]]:
    rows = chart_payload["rows"]
    closes = {parse_date(row["date"]): float(row["adjclose"]) for row in rows}
    ordered_dates = sorted(closes)
    returns: dict[date, float] = {}
    previous_close = None
    for day in ordered_dates:
        close = closes[day]
        returns[day] = 0.0 if previous_close is None else (close / previous_close) - 1.0
        previous_close = close
    return closes, ordered_dates, returns


def _dividend_yield(chart_payload: dict, asof: date, close: float) -> float:
    if close <= 0:
        return 0.0
    start = asof - timedelta(days=365)
    amount = 0.0
    for row in chart_payload.get("dividends", []):
        current = parse_date(row["date"])
        if start < current <= asof:
            amount += float(row["amount"])
    return amount / close


def _rolling_window(ordered_dates: list[date], values: dict[date, float], end_date: date, length: int) -> list[float]:
    if end_date not in ordered_dates:
        return []
    idx = ordered_dates.index(end_date)
    start_idx = max(0, idx - length + 1)
    return [values[day] for day in ordered_dates[start_idx : idx + 1]]


def _realized_wave(returns: dict[date, float], ordered_dates: list[date], asof: date) -> float | None:
    window = _rolling_window(ordered_dates, returns, asof, 30)
    if len(window) < 10:
        return None
    return annualize_volatility(window) * math.sqrt(5.0 / TRADING_DAYS)


def _market_price_proxy(
    stock_closes: dict[date, float],
    stock_dates: list[date],
    sector_closes: dict[date, float],
    asof: date,
    window_days: int,
    scale: float,
) -> float | None:
    if asof not in stock_dates:
        return None
    idx = stock_dates.index(asof)
    if idx < window_days:
        return None
    start_day = stock_dates[idx - window_days]
    sector_start = closest_previous_date(sorted(sector_closes), start_day)
    sector_end = closest_previous_date(sorted(sector_closes), asof)
    if sector_start is None or sector_end is None:
        return None
    stock_return = safe_div(stock_closes[asof], stock_closes[start_day]) - 1.0
    sector_return = safe_div(sector_closes[sector_end], sector_closes[sector_start]) - 1.0
    return tanh_score(stock_return - sector_return, scale)


def _market_state(spy_closes: dict[date, float], spy_dates: list[date], asof: date, window_days: int = 20) -> float | None:
    if asof not in spy_dates:
        return None
    idx = spy_dates.index(asof)
    if idx < window_days:
        return None
    start_day = spy_dates[idx - window_days]
    return safe_div(spy_closes[asof], spy_closes[start_day]) - 1.0


def _options_realized_skew_proxy(stock_returns: dict[date, float], stock_dates: list[date], asof: date, window_days: int) -> float | None:
    window = _rolling_window(stock_dates, stock_returns, asof, window_days)
    if len(window) < 8:
        return None
    downside = [abs(value) for value in window if value < 0]
    upside = [value for value in window if value > 0]
    if not downside and not upside:
        return 0.5
    downside_vol = stddev(downside) if len(downside) >= 2 else mean(downside)
    upside_vol = stddev(upside) if len(upside) >= 2 else mean(upside)
    if downside_vol == 0 and upside_vol == 0:
        return 0.5
    return clamp(safe_div(upside_vol, upside_vol + downside_vol), 0.0, 1.0)


def _lexical_sentiment(text: str, config: dict) -> float:
    lowered = text.lower()
    positives = sum(lowered.count(term.lower()) for term in config["management_sentiment"]["positive_terms"])
    negatives = sum(lowered.count(term.lower()) for term in config["management_sentiment"]["negative_terms"])
    return clamp((positives + 1.0) / (positives + negatives + 2.0), 0.0, 1.0)


def _management_text_from_fixtures(ticker: str, asof: date, fixture_data: dict) -> tuple[str, str, date] | None:
    texts = fixture_data.get("management_texts", {}).get(ticker, [])
    candidates = []
    for item in texts:
        current = parse_date(item["date"])
        if current <= asof and current >= asof - timedelta(days=120):
            candidates.append((current, item["source_type"], item["text"]))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    current, source_type, text = candidates[-1]
    return text, source_type, current


def _management_text_from_sec(
    firm: dict,
    asof: date,
    raw_dir: Path,
    user_agent: str,
    refresh: bool = False,
) -> tuple[str, str, date] | None:
    try:
        payloads = fetch_sec_submissions(firm["cik"], raw_dir, user_agent, refresh=refresh)
    except Exception:
        return None
    filing_rows = expand_submission_rows(payloads, {"8-K", "10-Q", "10-K"}, format_date(asof - timedelta(days=120)), format_date(asof))
    filing_rows = sorted(filing_rows, key=lambda item: item["filing_date"], reverse=True)
    for filing_row in filing_rows:
        filing_day = parse_date(filing_row["filing_date"])
        if filing_day > asof or filing_day < asof - timedelta(days=120):
            continue
        if filing_row["form"] == "8-K":
            bundle = fetch_filing_text_bundle(firm["cik"], filing_row, raw_dir, user_agent, refresh=refresh)
            release_docs = [item for item in bundle if item["source_type"] == "ir_press_release" and item["text"]]
            if release_docs:
                return release_docs[0]["text"], "ir_press_release", filing_day
            primary_docs = [item for item in bundle if item["text"]]
            if primary_docs:
                return primary_docs[0]["text"], "sec_primary_filing", filing_day
            continue
        primary_document = filing_row["primary_document"]
        if not primary_document:
            continue
        url = build_sec_document_url(firm["cik"], filing_row["accession_number"], primary_document)
        try:
            text = fetch_sec_document(url, raw_dir, user_agent, refresh=refresh)
        except Exception:
            continue
        cleaned = strip_html(text)
        if cleaned:
            return cleaned, "sec_filing_mda", filing_day
    return None


def _management_score(
    firm: dict,
    asof: date,
    config: dict,
    raw_dir: Path,
    refresh: bool = False,
    fixture_data: dict | None = None,
) -> tuple[float | None, str, str, date | None]:
    lookup = None
    if fixture_data is not None:
        lookup = _management_text_from_fixtures(firm["ticker"], asof, fixture_data)
    if lookup is None:
        lookup = _management_text_from_sec(firm, asof, raw_dir, config["sec"]["user_agent"], refresh=refresh)
    if lookup is None:
        return None, "missing", "missing", None
    text, source_type, source_date = lookup
    score = _lexical_sentiment(text, config)
    return score, source_type, config["management_sentiment"]["fallback_model"], source_date


def _authorization_balance_before_event(
    ledger: list[dict],
    ticker: str,
    event_day: date,
    company_facts: dict,
    sample_start: date,
) -> float:
    prior_authorizations = sum(
        float(row["authorization_amount"] or 0.0)
        for row in ledger
        if row["ticker"] == ticker and parse_date(row["announcement_date"]) < event_day
    )
    repurchase_rows, _ = _fact_rows(
        company_facts,
        "us-gaap",
        [
            "PaymentsForRepurchaseOfCommonStock",
            "StockRepurchasedAndRetiredDuringPeriodValue",
            "TreasuryStockValueAcquiredCostMethod",
        ],
    )
    cumulative = 0.0
    for row in _dedupe_period_rows(repurchase_rows, event_day - timedelta(days=1), 70, 110):
        end = parse_date(row["end"])
        if sample_start <= end < event_day:
            cumulative += float(row["val"])
    return max(prior_authorizations - cumulative, 0.0)


def _market_cap(company_facts: dict, closes: dict[date, float], asof: date) -> float | None:
    share_rows, _ = _fact_rows(company_facts, "dei", ["EntityCommonStockSharesOutstanding"])
    shares = _latest_instant_value(share_rows, asof)
    close_day = closest_previous_date(sorted(closes), asof)
    if shares is None or close_day is None:
        return None
    return shares * closes[close_day]


def _amazon_internal_particle(company_facts: dict, market_cap: float, asof: date) -> float | None:
    if market_cap <= 0:
        return None
    revenue_rows, _ = _fact_rows(company_facts, "us-gaap", ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"])
    operating_rows, _ = _fact_rows(company_facts, "us-gaap", ["OperatingIncomeLoss"])
    capex_rows, _ = _fact_rows(company_facts, "us-gaap", ["PaymentsToAcquirePropertyPlantAndEquipment"])

    revenue_ttm = _quarterly_flow_sum(revenue_rows, asof, quarters=4)
    revenue_q = _latest_quarter_value(revenue_rows, asof)
    operating_q = _latest_quarter_value(operating_rows, asof)
    capex_q = _latest_quarter_value(capex_rows, asof)

    prev_revenues = _previous_quarter_values(revenue_rows, asof, count=4)
    prev_operating = _previous_quarter_values(operating_rows, asof, count=4)
    prev_capex = _previous_quarter_values(capex_rows, asof, count=4)

    if revenue_ttm is None or revenue_q is None or operating_q is None:
        return None

    current_margin = safe_div(operating_q, revenue_q)
    prior_margins = [
        safe_div(op_value, rev_value)
        for op_value, rev_value in zip(prev_operating[-len(prev_revenues) :], prev_revenues)
        if rev_value != 0
    ]
    prior_margin = mean(prior_margins) if prior_margins else current_margin
    delta_margin = max(current_margin - prior_margin, 0.0)
    prior_capex = mean(prev_capex) if prev_capex else capex_q or 0.0
    reallocated_capex = max((capex_q or 0.0) - prior_capex, 0.0)
    return max((delta_margin * revenue_ttm + reallocated_capex) / market_cap, 0.0)


def _build_price_universe(config: dict, raw_dir: Path, refresh: bool = False, fixture_data: dict | None = None) -> dict[str, dict]:
    symbols = {firm["ticker"] for firm in config["firms"]}
    symbols.update(
        {
            config["market_data"]["market_symbol"],
            config["market_data"]["sector_symbol"],
            config["market_data"]["vix_symbol"],
        }
    )
    payloads: dict[str, dict] = {}
    for symbol in sorted(symbols):
        if fixture_data and symbol in fixture_data.get("price_history", {}):
            payloads[symbol] = fixture_data["price_history"][symbol]
            continue
        payloads[symbol] = fetch_yahoo_chart(
            symbol,
            config["sample"]["lookback_start"],
            config["sample"]["end"],
            raw_dir,
            config["market_data"]["chart_url_template"],
            refresh=refresh,
        )
    return payloads


def compute_feature_panel(
    ledger: list[dict],
    config: dict,
    raw_dir: Path,
    refresh: bool = False,
    fixture_data: dict | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    price_payloads = _build_price_universe(config, raw_dir, refresh=refresh, fixture_data=fixture_data)
    price_maps = {symbol: _close_lookup(payload) for symbol, payload in price_payloads.items()}
    company_facts_cache: dict[str, dict] = {}
    for firm in config["firms"]:
        if fixture_data and firm["ticker"] in fixture_data.get("company_facts", {}):
            company_facts_cache[firm["ticker"]] = fixture_data["company_facts"][firm["ticker"]]
        else:
            company_facts_cache[firm["ticker"]] = fetch_sec_company_facts(
                firm["cik"],
                raw_dir,
                config["sec"]["user_agent"],
                refresh=refresh,
            )

    market_symbol = config["market_data"]["market_symbol"]
    sector_symbol = config["market_data"]["sector_symbol"]
    vix_symbol = config["market_data"]["vix_symbol"]
    spy_closes, spy_dates, spy_returns = price_maps[market_symbol]
    sector_closes, _, _ = price_maps[sector_symbol]
    vix_closes, _, _ = price_maps[vix_symbol]
    firm_lookup = {item["ticker"]: item for item in config["firms"]}
    sample_start = parse_date(config["sample"]["start"])
    max_horizon = max(config["coherence"]["horizons"])

    feature_rows: list[dict] = []
    return_rows: list[dict] = []
    updated_ledger: list[dict] = []

    for row in ledger:
        ticker = row["ticker"]
        firm = firm_lookup[ticker]
        announcement_dt = parse_datetime(row["announcement_ts"])
        t0_date = map_announcement_to_t0(announcement_dt, spy_dates)
        updated_row = dict(row)
        updated_row["t0_date"] = format_date(t0_date) if t0_date else None

        stock_closes, stock_dates, stock_returns = price_maps[ticker]
        company_facts = company_facts_cache[ticker]
        if t0_date is None:
            updated_row["exclusion_reason"] = "missing_t0_mapping"
            updated_ledger.append(updated_row)
            continue
        asof = closest_previous_date(spy_dates, t0_date - timedelta(days=1))
        if asof is None:
            updated_row["exclusion_reason"] = "missing_pre_event_trading_day"
            updated_ledger.append(updated_row)
            continue

        market_cap = _market_cap(company_facts, stock_closes, asof)
        close_day = closest_previous_date(stock_dates, asof)
        close_value = stock_closes.get(close_day) if close_day else None
        dividend_yield = _dividend_yield(price_payloads[ticker], asof, close_value or 0.0)
        remaining_authorization = _authorization_balance_before_event(ledger, ticker, parse_date(row["announcement_date"]), company_facts, sample_start)
        if firm["particle_variant"] == "internal_reallocation":
            particle_amplitude = _amazon_internal_particle(company_facts, market_cap or 0.0, asof)
        else:
            particle_amplitude = None if market_cap in (None, 0.0) else safe_div(remaining_authorization, market_cap) + dividend_yield

        wave_amplitude = _realized_wave(stock_returns, stock_dates, asof)
        s_market = _market_price_proxy(
            stock_closes,
            stock_dates,
            sector_closes,
            asof,
            int(config["market_sentiment"]["price_proxy_window_days"]),
            float(config["market_sentiment"]["scale"]),
        )
        s_options = _options_realized_skew_proxy(
            stock_returns,
            stock_dates,
            asof,
            int(config["options_sentiment"]["realized_skew_window_days"]),
        )
        s_mgmt, s_mgmt_source, management_model, management_date = _management_score(
            firm,
            asof,
            config,
            raw_dir,
            refresh=refresh,
            fixture_data=fixture_data,
        )

        h_t = float(config["theta"]["h_t_default"])
        theta = compute_theta(s_mgmt, s_market, s_options, h_t=h_t)
        qii = compute_qii(particle_amplitude, wave_amplitude, theta)

        authorization_intensity = None if market_cap in (None, 0.0) else safe_div(float(row.get("authorization_amount") or 0.0), market_cap)
        market_state = _market_state(spy_closes, spy_dates, asof, window_days=20)
        vix_close_day = closest_previous_date(sorted(vix_closes), asof)
        vix_value = vix_closes.get(vix_close_day) if vix_close_day else None

        coverage_count = sum(value is not None for value in (s_mgmt, s_market, s_options))
        theta_source_parts = []
        if s_mgmt is not None:
            theta_source_parts.append("management_lexical_proxy")
        if s_market is not None:
            theta_source_parts.append("market_price_proxy")
        if s_options is not None:
            theta_source_parts.append("options_realized_skew_proxy")
        theta_source_variant = "+".join(theta_source_parts) if theta_source_parts else "missing"
        eligible = all(value is not None for value in (qii, market_state, vix_value))
        exclusion_reasons: list[str] = []
        if s_mgmt is None:
            exclusion_reasons.append("missing_management_text")
        if qii is None:
            exclusion_reasons.append("missing_qii")
        if market_state is None:
            exclusion_reasons.append("missing_market_state")
        if vix_value is None:
            exclusion_reasons.append("missing_vix")

        t0_idx = spy_dates.index(t0_date)
        car_by_horizon: dict[int, float | None] = {}
        cumulative = 0.0
        base_close = stock_closes.get(t0_date) or stock_closes.get(close_day or t0_date)
        post_path: list[float] = []
        for offset in range(0, max_horizon + 1):
            if t0_idx + offset >= len(spy_dates):
                car_by_horizon[offset] = None
                continue
            current_day = spy_dates[t0_idx + offset]
            current_stock_return = stock_returns.get(current_day)
            current_market_return = spy_returns.get(current_day)
            if current_stock_return is None or current_market_return is None:
                car_by_horizon[offset] = None
                continue
            cumulative += current_stock_return - current_market_return
            car_by_horizon[offset] = cumulative
            if current_day in stock_closes and base_close:
                post_path.append((stock_closes[current_day] / base_close) - 1.0)

        drawdown_window = post_path[: int(config["entanglement"]["tail_horizon_days"]) + 1]
        post_event_drawdown = min(drawdown_window) if drawdown_window else None
        car_0_5 = car_by_horizon.get(5)
        if car_0_5 is None:
            eligible = False
            exclusion_reasons.append("missing_car_0_5")

        feature_row = {
            "event_id": row["event_id"],
            "ticker": ticker,
            "firm": ticker,
            "company_name": row["company_name"],
            "archetype": row["archetype"],
            "event_family": row["event_family"],
            "particle_variant": row["particle_variant"],
            "announcement_ts": row["announcement_ts"],
            "announcement_date": row["announcement_date"],
            "t0_date": format_date(t0_date),
            "data_tier": "public_proxy",
            "reconstruction_status": row["reconstruction_status"],
            "source_urls": row["source_urls"],
            "event_title": row["event_title"],
            "authorization_amount": row.get("authorization_amount"),
            "dividend_per_share": row.get("dividend_per_share"),
            "market_cap_t1": market_cap,
            "remaining_authorization_t1": remaining_authorization,
            "trailing_dividend_yield_t1": dividend_yield,
            "particle_amplitude": particle_amplitude,
            "wave_amplitude": wave_amplitude,
            "wave_source": "realized_vol_proxy" if wave_amplitude is not None else "missing",
            "authorization_intensity": authorization_intensity,
            "market_state_20d": market_state,
            "vix_t1": vix_value,
            "s_mgmt": s_mgmt,
            "s_mgmt_source": s_mgmt_source,
            "management_model": management_model,
            "management_text_date": format_date(management_date) if management_date else None,
            "s_market": s_market,
            "s_market_source": "market_price_proxy" if s_market is not None else "missing",
            "s_options": s_options,
            "s_options_source": "options_realized_skew_proxy" if s_options is not None else "missing",
            "theta_degrees": theta,
            "theta_source_variant": theta_source_variant,
            "theta_component_coverage": f"{coverage_count}/3",
            "h_t": h_t,
            "qii": qii,
            "car_0_5": car_0_5,
            "post_event_drawdown_50d": post_event_drawdown,
            "primary_regression_eligible": eligible,
            "exclusion_reason": ";".join(sorted(set(exclusion_reasons))),
        }
        feature_rows.append(feature_row)

        for horizon in config["coherence"]["horizons"]:
            return_rows.append(
                {
                    "event_id": row["event_id"],
                    "ticker": ticker,
                    "horizon_days": horizon,
                    "car": car_by_horizon.get(horizon),
                    "data_tier": "public_proxy",
                }
            )

        updated_row["t0_date"] = format_date(t0_date)
        updated_row["exclusion_reason"] = feature_row["exclusion_reason"]
        updated_ledger.append(updated_row)

    return updated_ledger, feature_rows, return_rows
