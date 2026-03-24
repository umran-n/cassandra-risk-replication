# Phase 3 Summary Report

## Top 20 Lowest-RSI Days

Table 1 candidate for Paper 2. Days are sorted by RSI ascending; the dominant event and dominant P/S/C/T component are flagged for each day.

| Date | RSI | Total Hazard | Dominant Event | Dominant Category | Dominant Component | P Share | S Share | C Share | T Share |
| --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| 2022-02-24 | 0.093 | 9.792 | ukraine_invasion_2022 | Kinetic | S_severity | 24.69% | 25.13% | 25.05% | 25.13% |
| 2023-06-02 | 0.095 | 9.512 | us_debt_ceiling_2023 | Sovereign | C_velocity | 24.41% | 21.87% | 28.03% | 25.69% |
| 2023-06-01 | 0.096 | 9.433 | us_debt_ceiling_2023 | Sovereign | C_velocity | 24.25% | 21.92% | 28.10% | 25.73% |
| 2023-05-31 | 0.096 | 9.409 | us_debt_ceiling_2023 | Sovereign | C_velocity | 24.22% | 21.93% | 28.12% | 25.73% |
| 2023-05-30 | 0.098 | 9.249 | us_debt_ceiling_2023 | Sovereign | C_velocity | 23.88% | 22.04% | 28.26% | 25.83% |
| 2023-05-26 | 0.103 | 8.679 | us_debt_ceiling_2023 | Sovereign | C_velocity | 23.19% | 22.41% | 28.24% | 26.15% |
| 2023-05-25 | 0.106 | 8.449 | us_debt_ceiling_2023 | Sovereign | C_velocity | 22.79% | 22.58% | 28.34% | 26.29% |
| 2022-02-23 | 0.114 | 7.751 | ukraine_invasion_2022 | Kinetic | S_severity | 20.60% | 26.49% | 26.41% | 26.49% |
| 2023-05-24 | 0.123 | 7.131 | us_debt_ceiling_2023 | Sovereign | C_velocity | 23.20% | 23.03% | 27.14% | 26.63% |
| 2023-05-23 | 0.124 | 7.082 | us_debt_ceiling_2023 | Sovereign | C_velocity | 23.19% | 23.07% | 27.07% | 26.67% |
| 2020-03-16 | 0.125 | 7.005 | covid_crash_2020 | Sovereign | T_persistence | 23.95% | 21.77% | 27.08% | 27.21% |
| 2020-03-17 | 0.125 | 6.983 | covid_crash_2020 | Sovereign | T_persistence | 23.89% | 21.79% | 27.10% | 27.23% |
| 2020-03-18 | 0.126 | 6.918 | covid_crash_2020 | Sovereign | T_persistence | 23.72% | 21.83% | 27.16% | 27.29% |
| 2020-03-13 | 0.127 | 6.879 | covid_crash_2020 | Sovereign | T_persistence | 23.86% | 21.87% | 26.93% | 27.34% |
| 2023-05-19 | 0.127 | 6.851 | us_debt_ceiling_2023 | Sovereign | T_persistence | 23.04% | 23.28% | 26.80% | 26.88% |
| 2023-05-22 | 0.128 | 6.825 | us_debt_ceiling_2023 | Sovereign | C_velocity | 22.61% | 23.31% | 27.20% | 26.89% |
| 2020-03-19 | 0.128 | 6.813 | covid_crash_2020 | Sovereign | T_persistence | 23.44% | 21.91% | 27.25% | 27.39% |
| 2020-03-12 | 0.128 | 6.802 | covid_crash_2020 | Sovereign | T_persistence | 23.78% | 21.93% | 26.87% | 27.41% |
| 2020-03-11 | 0.130 | 6.715 | covid_crash_2020 | Sovereign | T_persistence | 23.67% | 22.00% | 26.82% | 27.50% |
| 2023-05-18 | 0.130 | 6.686 | us_debt_ceiling_2023 | Sovereign | T_persistence | 22.70% | 23.43% | 26.84% | 27.02% |

## Top Hazard Contributors By Event

Cumulative hazard share over the full backtest window. This addresses whether the result is event-specific or distributed across the event set.

| Rank | Event | Category | Cum Hazard | Hazard Share | Active Days | First Date | Last Date |
| ---: | --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | covid_crash_2020 | Sovereign | 205.337 | 24.77% | 60 | 2020-01-21 | 2020-04-15 |
| 2 | us_debt_ceiling_2023 | Sovereign | 170.091 | 20.52% | 29 | 2023-04-24 | 2023-06-02 |
| 3 | china_taiwan_2024 | Kinetic | 156.683 | 18.90% | 439 | 2023-04-06 | 2025-01-03 |
| 4 | rate_hike_shock_2022 | Monetary | 93.398 | 11.27% | 72 | 2022-04-01 | 2022-07-15 |
| 5 | oct_selloff_2023 | Monetary | 93.175 | 11.24% | 151 | 2023-05-25 | 2023-12-29 |
| 6 | svb_contagion_2023 | Sovereign | 46.526 | 5.61% | 27 | 2023-02-15 | 2023-03-24 |
| 7 | eu_banking_contagion_2024 | Sovereign | 35.412 | 4.27% | 29 | 2024-10-21 | 2024-11-29 |
| 8 | ukraine_invasion_2022 | Kinetic | 19.010 | 2.29% | 3 | 2022-02-22 | 2022-02-24 |
| 9 | aug_volatility_2024 | Technology | 9.394 | 1.13% | 25 | 2024-07-15 | 2024-08-16 |

## Top Hazard Contributors By Category

| Rank | Category | Cum Hazard | Hazard Share | Active Event-Days |
| ---: | --- | ---: | ---: | ---: |
| 1 | Sovereign | 457.365 | 55.17% | 145 |
| 2 | Monetary | 186.573 | 22.51% | 223 |
| 3 | Kinetic | 175.694 | 21.19% | 442 |
| 4 | Technology | 9.394 | 1.13% | 25 |

## Average P/S/C/T Shares By Regime Bucket

Average component shares by RSI bucket. This is the transparency layer for how the hazard formula changes character across regimes.

| Regime Bucket | Days | Avg RSI | Avg Hazard | Avg P Share | Avg S Share | Avg C Share | Avg T Share | Dominant Component |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| RSI < 0.3 (high hazard) | 98 | 0.194 | 4.826 | 18.05% | 23.32% | 28.94% | 29.69% | T_persistence |
| 0.3 <= RSI <= 0.7 (transition) | 328 | 0.553 | 0.906 | 5.29% | 28.06% | 35.26% | 31.38% | C_velocity |
| RSI > 0.7 (low hazard) | 838 | 0.948 | 0.070 | 0.44% | 7.17% | 7.20% | 6.07% | C_velocity |
