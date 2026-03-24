from __future__ import annotations


VALID_STRUCTURAL_THEMES = {
    "geopolitical",
    "monetary_policy",
    "fiscal_debt",
    "electoral",
    "systemic_credit",
    "trade_technology",
}


EVENT_STRUCTURAL_THEME_MAP = {
    "covid_crash_2020": "systemic_credit",
    "ukraine_invasion_2022": "geopolitical",
    "rate_hike_shock_2022": "monetary_policy",
    "svb_contagion_2023": "systemic_credit",
    "us_debt_ceiling_2023": "fiscal_debt",
    "oct_selloff_2023": "monetary_policy",
    "china_taiwan_2024": "geopolitical",
    "aug_volatility_2024": "trade_technology",
    "eu_banking_contagion_2024": "systemic_credit",
}


CATEGORY_STRUCTURAL_THEME_MAP = {
    "Kinetic": "geopolitical",
    "Monetary": "monetary_policy",
    "Trade": "trade_technology",
    "Technology": "trade_technology",
    "Sovereign": "fiscal_debt",
    "None": "trade_technology",
}


def infer_structural_theme(record: dict) -> str:
    explicit = record.get("structural_theme")
    if explicit:
        if explicit not in VALID_STRUCTURAL_THEMES:
            raise ValueError(f"Unsupported structural_theme: {explicit}")
        return explicit

    event_id = record.get("event_id") or record.get("forced_event_id")
    if event_id and event_id in EVENT_STRUCTURAL_THEME_MAP:
        return EVENT_STRUCTURAL_THEME_MAP[event_id]

    category = record.get("category") or record.get("forced_category")
    if category and category in CATEGORY_STRUCTURAL_THEME_MAP:
        return CATEGORY_STRUCTURAL_THEME_MAP[category]

    return "trade_technology"
