# Phase 5.6 Geopolitical Expansion Report

This experiment tests a governed geopolitical add-on set against the published `V5_Becker_top5_cap` stack.

## Stack Comparison

| Version | Loaded Events | Sortino | CAGR | Daily MDD | Avg Position |
| --- | ---: | ---: | ---: | ---: | ---: |
| V5_Becker_top5_cap | 27 | 0.323 | 7.13% | -33.72% | 73.05% |
| V5_geo_only | 39 | 0.236 | 5.82% | -33.72% | 66.80% |
| V5_Becker_top5_cap_geo | 34 | 0.330 | 7.24% | -33.72% | 72.54% |
| V5_Becker_top5_cap_geo_calibrated | 34 | 0.318 | 7.05% | -33.72% | 74.66% |

## Readout

- `V5_geo_only` vs baseline stack: Sortino `-0.087`, CAGR `-1.32pp`.
- `V5_Becker_top5_cap_geo` vs baseline stack: Sortino `+0.007`, CAGR `+0.10pp`.
- `V5_Becker_top5_cap_geo_calibrated` vs baseline stack: Sortino `-0.005`, CAGR `-0.08pp`.
- Geopolitical calibration delta over uncalibrated geo stack: Sortino `-0.012`, CAGR `-0.18pp`.

## Calibrated Add-On Hazard Contributors

| Event | Cum Hazard | Share of Total Hazard | Share of Geopolitical Hazard | First Date | Last Date |
| --- | ---: | ---: | ---: | --- | --- |
| geopolitical_israel_x_hamas_ceasefire_before_september_2024 | 94.802 | 4.41% | 15.87% | 2024-05-30 | 2024-08-30 |
| geopolitical_will_israel_invade_lebanon_before_november_2024 | 40.706 | 1.89% | 6.82% | 2024-08-08 | 2024-10-04 |
| geopolitical_another_israeli_military_action_against_iran_in_2024_2025 | 28.180 | 1.31% | 4.72% | 2024-10-29 | 2024-12-31 |
| geopolitical_russia_x_ukraine_ceasefire_in_2024_2025 | 25.282 | 1.18% | 4.23% | 2024-09-17 | 2024-12-31 |
| geopolitical_israel_withdraws_from_gaza_in_2024_2025 | 14.975 | 0.70% | 2.51% | 2024-10-21 | 2024-12-31 |
| geopolitical_iran_strike_on_israel_before_december_2024 | 12.205 | 0.57% | 2.04% | 2024-11-01 | 2024-11-29 |
| geopolitical_u_s_military_action_against_iran_before_november_2024 | 8.673 | 0.40% | 1.45% | 2024-09-24 | 2024-11-01 |
