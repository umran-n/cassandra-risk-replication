# Expansion Diagnostic Report

## Scope

- Baseline V5 approved universe: `38` approved events, with `32` active Polymarket histories and `6` Metaculus placeholders skipped for lack of time series.
- V5 baseline Cassandra metrics: Sortino `0.231`, CAGR `5.75%`, daily MDD `-33.72%`, avg position `67.26%`.
- Same-run Vol Target Sortino reference: `0.836`.

## Theme-Level Ablation

| Theme Removed | Active Events | Sortino | CAGR | MDD | Avg Position |
| --- | ---: | ---: | ---: | ---: | ---: |
| monetary_policy | 12 | 0.341 | 7.42% | -33.72% | 77.86% |
| geopolitical | 26 | 0.257 | 6.14% | -33.72% | 71.13% |
| electoral | 28 | 0.276 | 6.42% | -33.72% | 69.03% |

Interpretation:
- Removing `monetary_policy` produced the strongest Sortino recovery, which is the cleanest first-pass test of the over-warning hypothesis.

## Monetary Concentration

Top monetary-policy contributors ranked by cumulative hazard contribution across the V5 backtest window.

| Rank | Event | Cum Hazard | Theme Share | Total Share | Active Days |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | monetary_policy_will_the_fed_increase_interest_rates_by_25_bps_after_its_march_meeting_2023 | 192.903 | 11.57% | 5.12% | 65 |
| 2 | monetary_policy_will_the_fed_raise_interest_rates_by_0_bps_after_its_september_meeting_2023 | 165.526 | 9.92% | 4.40% | 44 |
| 3 | monetary_policy_will_the_fed_increase_interest_rates_by_50_bps_after_its_february_meeting_2023 | 158.403 | 9.50% | 4.21% | 86 |
| 4 | monetary_policy_will_the_fed_raise_interest_rates_by_0_bps_after_its_december_meeting_2023 | 144.501 | 8.66% | 3.84% | 36 |
| 5 | monetary_policy_fed_rate_cut_by_may_1_2024 | 134.486 | 8.06% | 3.57% | 101 |

## RSI Drag By Quarter

Flagged quarters are positive-SPY quarters where average position stayed below 85% and the Cassandra quarter return lagged SPY by more than 3 percentage points.

| Quarter | Avg RSI | Avg Position | SPY Return | Cassandra Return | Gap vs SPY | Flagged |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2022Q1 | 1.000 | 100.00% | -4.61% | -4.61% | 0.00% | no |
| 2022Q2 | 1.000 | 100.00% | -16.11% | -16.11% | 0.00% | no |
| 2022Q3 | 1.000 | 100.00% | -4.93% | -4.93% | 0.00% | no |
| 2022Q4 | 0.922 | 92.25% | 7.56% | 7.65% | -0.09% | no |
| 2023Q1 | 0.417 | 41.69% | 7.46% | 7.16% | 0.29% | no |
| 2023Q2 | 0.132 | 13.21% | 8.68% | 0.07% | 8.61% | YES |
| 2023Q3 | 0.182 | 18.20% | -3.22% | -0.49% | -2.73% | no |
| 2023Q4 | 0.231 | 23.14% | 11.64% | 1.72% | 9.92% | YES |
| 2024Q1 | 0.111 | 11.14% | 10.39% | 1.18% | 9.21% | YES |
| 2024Q2 | 0.138 | 13.76% | 4.38% | -0.26% | 4.63% | YES |
| 2024Q3 | 0.133 | 13.26% | 5.75% | -0.02% | 5.77% | YES |
| 2024Q4 | 0.141 | 14.15% | 2.49% | -1.31% | 3.80% | YES |

## Findings

- The clearest missed-recovery quarters were:
  - `2023Q4`: avg position `23.14%`, SPY `11.64%`, Cassandra `1.72%`, gap `9.92%`.
  - `2024Q1`: avg position `11.14%`, SPY `10.39%`, Cassandra `1.18%`, gap `9.21%`.
  - `2023Q2`: avg position `13.21%`, SPY `8.68%`, Cassandra `0.07%`, gap `8.61%`.
  - `2024Q3`: avg position `13.26%`, SPY `5.75%`, Cassandra `-0.02%`, gap `5.77%`.
  - `2024Q2`: avg position `13.76%`, SPY `4.38%`, Cassandra `-0.26%`, gap `4.63%`.
  - `2024Q4`: avg position `14.15%`, SPY `2.49%`, Cassandra `-1.31%`, gap `3.80%`.
- The top monetary-policy event was `monetary_policy_will_the_fed_increase_interest_rates_by_25_bps_after_its_march_meeting_2023` at `11.57%` of the theme hazard, which indicates whether the damage is concentrated or spread across the rate-cycle stack.
- If monetary removal improves Sortino materially while geopolitical and electoral removal do not, the degradation is best explained as chronic macro over-warning rather than broad event-universe failure.
