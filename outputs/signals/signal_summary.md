# Unified Signal API Summary

- Governed families loaded: `54`
- Discovered candidate families: `31`
- Selected live signals: `4`
- Current governed RSI: `0.1915`
- Current total hazard: `4.2218`
- Dominant theme: `monetary_policy`
- Dominant event family: `monetary_policy_no_change_in_fed_interest_rates_after_2024_september_meeting_2024`

## Source Status

| Source | Reachable | Markets | Notes |
| --- | --- | ---: | --- |
| kalshi | True | 519 | Public live catalog fetched from Kalshi /trade-api/v2/events with nested markets. |
| manifold | True | 10 | Public live catalog fetched from /v0/markets. |
| metaculus | False | 0 | Missing credentials in env var METACULUS_API_TOKEN. |
| polymarket | True | 270 | Public live catalog fetched from Gamma /events ordered by 24h volume. |

## Top Selected Signals

| Event Family | Theme | Source | Probability | Calibration | Theme Cap |
| --- | --- | --- | ---: | --- | --- |
| geopolitical_israel_military_action_against_iran_by_end_of_2024_2024 | geopolitical | polymarket | 0.000 | none | True |
| monetary_policy_no_change_in_fed_interest_rates_after_2024_september_meeting_2024 | monetary_policy | polymarket | 0.926 | becker | True |
| monetary_policy_will_the_fed_decrease_interest_rates_by_25_bps_after_its_january_meeting_2024 | monetary_policy | polymarket | 0.014 | becker | True |
| monetary_policy_will_the_fed_increase_interest_rates_by_0_bps_after_its_june_meeting_2023 | monetary_policy | polymarket | 0.030 | becker | True |
