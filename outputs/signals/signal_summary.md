# Unified Signal API Summary

- Governed families loaded: `54`
- Discovered candidate families: `31`
- Selected live signals: `3`
- Current governed RSI: `0.7096`
- Current total hazard: `0.4093`
- Dominant theme: `monetary_policy`
- Dominant event family: `monetary_policy_fed_emergency_rate_cut_in_2024_2025`

## Source Status

| Source | Reachable | Markets | Notes |
| --- | --- | ---: | --- |
| kalshi | True | 519 | Public live catalog fetched from Kalshi /trade-api/v2/events with nested markets. |
| manifold | True | 14 | Public live catalog fetched from /v0/markets. |
| metaculus | False | 0 | Missing credentials in env var METACULUS_API_TOKEN. |
| polymarket | True | 270 | Public live catalog fetched from Gamma /events ordered by 24h volume. |

## Top Selected Signals

| Event Family | Theme | Source | Probability | Calibration | Theme Cap |
| --- | --- | --- | ---: | --- | --- |
| geopolitical_another_israeli_military_action_against_iran_in_2024_2025 | geopolitical | polymarket | 0.001 | none | True |
| geopolitical_russia_x_ukraine_ceasefire_in_2024_2025 | geopolitical | polymarket | 0.002 | none | True |
| monetary_policy_fed_emergency_rate_cut_in_2024_2025 | monetary_policy | polymarket | 0.235 | becker | True |
