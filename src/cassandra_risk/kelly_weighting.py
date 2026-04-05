from __future__ import annotations

import copy

from .becker_calibration import calibration_params_for_row
from .utils import clamp


def becker_corrected_probability(raw_probability: float, efficiency_gap: float) -> float:
    return clamp(float(raw_probability) - float(efficiency_gap), 0.0, 1.0)


def kelly_fraction(becker_probability: float) -> float:
    probability = clamp(float(becker_probability), 0.0, 1.0)
    return (2.0 * probability) - 1.0


def scaled_kelly_fraction(becker_probability: float, fraction_scale: float = 1.0) -> float:
    return kelly_fraction(becker_probability) * float(fraction_scale)


def kelly_weighted_probability(becker_probability: float, fraction_scale: float = 1.0) -> float:
    probability = clamp(float(becker_probability), 0.0, 1.0)
    return probability * scaled_kelly_fraction(probability, fraction_scale)


def apply_kelly_weighting(
    daily_events: dict[str, dict[str, dict]],
    config: dict,
    _dates: list[str] | None = None,
    *,
    fraction_scale: float = 1.0,
) -> dict[str, dict[str, dict]]:
    updated: dict[str, dict[str, dict]] = {}
    for day_string, events in daily_events.items():
        day_events: dict[str, dict] = {}
        for event_id, row in events.items():
            item = copy.deepcopy(row)
            params = calibration_params_for_row(item, config)
            original = float(item.get("becker_original_probability", item["probability"]))
            gap = 0.0 if params is None else float(params["gap"])
            becker_probability = becker_corrected_probability(original, gap)
            fraction = scaled_kelly_fraction(becker_probability, fraction_scale)
            weighted_probability = kelly_weighted_probability(becker_probability, fraction_scale)

            item["probability"] = weighted_probability
            item["kelly_weighting"] = "enabled"
            item["kelly_fraction_scale"] = float(fraction_scale)
            item["kelly_original_probability"] = original
            item["kelly_becker_probability"] = becker_probability
            item["kelly_efficiency_gap"] = gap
            item["kelly_fraction"] = fraction
            item["kelly_weighted_probability"] = weighted_probability
            day_events[event_id] = item
        updated[day_string] = day_events
    return updated
