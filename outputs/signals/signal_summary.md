# Unified Signal API Summary

- Governed families loaded: `54`
- Discovered candidate families: `31`
- Selected live signals: `0`
- Current governed RSI: `1.0000`
- Current total hazard: `0.0000`
- Dominant theme: ``
- Dominant event family: ``

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
