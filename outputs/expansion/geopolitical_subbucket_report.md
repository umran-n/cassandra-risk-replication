# Phase 5.7 Geopolitical Sub-Bucket Calibration Report

This experiment holds the governed geopolitical add-on set fixed and changes only the calibration granularity.

## Comparison

| Version | Loaded Events | Sortino | CAGR | Daily MDD | Avg Position |
| --- | ---: | ---: | ---: | ---: | ---: |
| V5_Becker_top5_cap_geo | 34 | 0.330 | 7.24% | -33.72% | 72.54% |
| V5_Becker_top5_cap_geo_flat | 34 | 0.318 | 7.05% | -33.72% | 74.66% |
| V5_Becker_top5_cap_geo_subbucket | 34 | 0.316 | 7.03% | -33.72% | 74.61% |

## Readout

- Flat calibrated geo vs published best row: Sortino `-0.012`, CAGR `-0.18pp`.
- Sub-bucket calibrated geo vs published best row: Sortino `-0.014`, CAGR `-0.20pp`.
- Sub-bucket delta over flat geo calibration: Sortino `-0.001`, CAGR `-0.02pp`.

## Sub-Bucket Constants

| Sub-Bucket | Becker Gap | Longshot Band | Horizon Profile |
| --- | ---: | --- | --- |
| conflict_escalation | 0.0891 | (0.10, 0.90) | open |
| ceasefire_deescalation | 0.0412 | (0.20, 0.80) | medium |
| great_power_intervention | 0.0958 | (0.05, 0.95) | open |
| regime_transition | 0.0634 | (0.15, 0.85) | long |
