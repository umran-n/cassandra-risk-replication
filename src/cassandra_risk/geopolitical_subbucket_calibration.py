from __future__ import annotations


GEO_SUBBUCKET_GAPS = {
    "conflict_escalation": {
        "becker_gap": 0.0891,
        "horizon_profile": "open",
        "longshot_band": (0.10, 0.90),
        "examples": ["US strikes Iran", "Taiwan Strait incident"],
    },
    "ceasefire_deescalation": {
        "becker_gap": 0.0412,
        "horizon_profile": "medium",
        "longshot_band": (0.20, 0.80),
        "examples": ["Ukraine ceasefire by EOY", "Gaza ceasefire"],
    },
    "great_power_intervention": {
        "becker_gap": 0.0958,
        "horizon_profile": "open",
        "longshot_band": (0.05, 0.95),
        "examples": ["NATO Article 5 invocation", "China Taiwan military action"],
    },
    "regime_transition": {
        "becker_gap": 0.0634,
        "horizon_profile": "long",
        "longshot_band": (0.15, 0.85),
        "examples": ["Khamenei out as Supreme Leader", "Putin removal"],
    },
}


CHANNEL_TO_SUBBUCKET = {
    "gaza_ceasefire_2024": "ceasefire_deescalation",
    "ukraine_ceasefire_2024": "ceasefire_deescalation",
    "gaza_withdrawal_2024": "ceasefire_deescalation",
    "lebanon_escalation": "conflict_escalation",
    "iran_retaliation": "conflict_escalation",
    "israel_iran_escalation": "conflict_escalation",
    "us_iran_escalation": "great_power_intervention",
}


def calibration_metadata_for_channel(channel: str) -> dict:
    subbucket = CHANNEL_TO_SUBBUCKET[channel]
    payload = GEO_SUBBUCKET_GAPS[subbucket]
    lower, upper = payload["longshot_band"]
    return {
        "calibration_subbucket": subbucket,
        "horizon_profile": payload["horizon_profile"],
        "subbucket_becker_gap": payload["becker_gap"],
        "subbucket_longshot_lower": lower,
        "subbucket_longshot_upper": upper,
    }


def infer_geopolitical_subbucket(title: str) -> str:
    text = (title or "").lower()
    if "ceasefire" in text or "withdraw" in text:
        return "ceasefire_deescalation"
    if "article 5" in text or "u.s. military action" in text or "us military action" in text:
        return "great_power_intervention"
    if "supreme leader" in text or "out as" in text or "removal" in text or "resign" in text:
        return "regime_transition"
    return "conflict_escalation"


def calibration_metadata_for_title(title: str) -> dict:
    subbucket = infer_geopolitical_subbucket(title)
    payload = GEO_SUBBUCKET_GAPS[subbucket]
    lower, upper = payload["longshot_band"]
    return {
        "calibration_subbucket": subbucket,
        "horizon_profile": payload["horizon_profile"],
        "subbucket_becker_gap": payload["becker_gap"],
        "subbucket_longshot_lower": lower,
        "subbucket_longshot_upper": upper,
    }
