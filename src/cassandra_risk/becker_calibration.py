from __future__ import annotations

import copy

from .utils import clamp


EFFICIENCY_GAPS = {
    "monetary_policy": 0.0017,
    "geopolitical": 0.0732,
    "electoral": 0.0102,
    "trade_technology": 0.0269,
    "fiscal_debt": 0.0102,
    "systemic_credit": 0.0102,
}


def becker_config(config: dict | None) -> dict:
    if not config:
        return {}
    return config.get("becker_calibration", {})


def efficiency_gap_for_theme(structural_theme: str | None, config: dict | None = None) -> float:
    theme = structural_theme or ""
    gaps = copy.deepcopy(EFFICIENCY_GAPS)
    gaps.update(becker_config(config).get("efficiency_gaps", {}))
    return float(gaps.get(theme, 0.0))


def shrink_toward_center(probability: float, gap: float) -> float:
    return 0.5 + (probability - 0.5) * (1.0 - gap)


def calibrate_probability(probability: float, structural_theme: str | None, config: dict | None = None) -> tuple[float, dict]:
    settings = becker_config(config)
    lower = float(settings.get("longshot_lower", 0.20))
    upper = float(settings.get("longshot_upper", 0.80))
    gap = efficiency_gap_for_theme(structural_theme, config)
    original = clamp(float(probability), 0.0, 1.0)

    calibrated = shrink_toward_center(original, gap)
    longshot_applied = original < lower or original > upper
    if longshot_applied:
        calibrated = shrink_toward_center(calibrated, gap)

    calibrated = clamp(calibrated, 0.0, 1.0)
    metadata = {
        "becker_efficiency_gap": gap,
        "becker_original_probability": original,
        "becker_longshot_compressed": longshot_applied,
        "becker_calibrated_probability": calibrated,
    }
    return calibrated, metadata


def apply_becker_calibration(
    daily_events: dict[str, dict[str, dict]],
    config: dict,
    _dates: list[str] | None = None,
) -> dict[str, dict[str, dict]]:
    if not becker_config(config).get("enabled", False):
        return {
            day: {event_id: copy.deepcopy(row) for event_id, row in events.items()}
            for day, events in daily_events.items()
        }

    updated: dict[str, dict[str, dict]] = {}
    for day_string, events in daily_events.items():
        day_events: dict[str, dict] = {}
        for event_id, row in events.items():
            item = copy.deepcopy(row)
            calibrated_probability, metadata = calibrate_probability(
                float(item["probability"]),
                item.get("structural_theme"),
                config,
            )
            item["probability"] = calibrated_probability
            item["becker_calibration"] = "enabled"
            for key, value in metadata.items():
                item[key] = value
            day_events[event_id] = item
        updated[day_string] = day_events
    return updated
