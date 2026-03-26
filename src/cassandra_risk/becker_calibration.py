from __future__ import annotations

import copy

from .signal_contract import SignalContract, ensure_signal_contract
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


def longshot_thresholds_for_theme(structural_theme: str | None, config: dict | None = None) -> tuple[float, float]:
    settings = becker_config(config)
    lower = float(settings.get("longshot_lower", 0.20))
    upper = float(settings.get("longshot_upper", 0.80))
    theme = structural_theme or ""
    theme_thresholds = settings.get("theme_longshot_thresholds", {}).get(theme)
    if isinstance(theme_thresholds, (list, tuple)) and len(theme_thresholds) == 2:
        return float(theme_thresholds[0]), float(theme_thresholds[1])
    return lower, upper


def calibration_params_for_row(row: dict, config: dict | None = None) -> dict | None:
    settings = becker_config(config)
    theme = row.get("structural_theme") or ""
    if theme in set(settings.get("skip_themes", [])):
        return None

    subbucket = row.get("calibration_subbucket")
    subbucket_gaps = settings.get("subbucket_efficiency_gaps", {})
    if subbucket and subbucket in subbucket_gaps:
        lower, upper = longshot_thresholds_for_theme(theme, config)
        thresholds = settings.get("subbucket_longshot_thresholds", {}).get(subbucket)
        if isinstance(thresholds, (list, tuple)) and len(thresholds) == 2:
            lower, upper = float(thresholds[0]), float(thresholds[1])
        return {
            "gap": float(subbucket_gaps[subbucket]),
            "lower": lower,
            "upper": upper,
            "key": str(subbucket),
            "scope": "subbucket",
        }

    lower, upper = longshot_thresholds_for_theme(theme, config)
    return {
        "gap": efficiency_gap_for_theme(theme, config),
        "lower": lower,
        "upper": upper,
        "key": theme,
        "scope": "theme",
    }


def efficiency_gap_for_theme(structural_theme: str | None, config: dict | None = None) -> float:
    theme = structural_theme or ""
    gaps = copy.deepcopy(EFFICIENCY_GAPS)
    gaps.update(becker_config(config).get("efficiency_gaps", {}))
    return float(gaps.get(theme, 0.0))


def shrink_toward_center(probability: float, gap: float) -> float:
    return 0.5 + (probability - 0.5) * (1.0 - gap)


def calibrate_probability(probability: float, structural_theme: str | None, config: dict | None = None) -> tuple[float, dict]:
    lower, upper = longshot_thresholds_for_theme(structural_theme, config)
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
            params = calibration_params_for_row(item, config)
            if params is None:
                item["becker_calibration"] = "skipped"
                item["becker_calibration_scope"] = "skipped"
                item["becker_calibration_key"] = item.get("structural_theme") or ""
            else:
                original = clamp(float(item["probability"]), 0.0, 1.0)
                calibrated = shrink_toward_center(original, float(params["gap"]))
                longshot_applied = original < float(params["lower"]) or original > float(params["upper"])
                if longshot_applied:
                    calibrated = shrink_toward_center(calibrated, float(params["gap"]))
                calibrated = clamp(calibrated, 0.0, 1.0)
                item["probability"] = calibrated
                item["becker_calibration"] = "enabled"
                item["becker_efficiency_gap"] = float(params["gap"])
                item["becker_original_probability"] = original
                item["becker_longshot_compressed"] = longshot_applied
                item["becker_calibrated_probability"] = calibrated
                item["becker_calibration_scope"] = str(params["scope"])
                item["becker_calibration_key"] = str(params["key"])
            day_events[event_id] = item
        updated[day_string] = day_events
    return updated


class BeckerCalibrationLayer:
    @staticmethod
    def apply(contract: SignalContract | dict, config: dict | None = None) -> SignalContract:
        typed = ensure_signal_contract(contract)
        calibrated, metadata = calibrate_probability(float(typed.probability_raw or 0.0), typed.structural_theme, config or {})
        return typed.with_updates(
            probability_calibrated=calibrated,
            efficiency_gap_applied=float(metadata.get("becker_efficiency_gap") or 0.0),
            calibration_applied="becker",
        )
