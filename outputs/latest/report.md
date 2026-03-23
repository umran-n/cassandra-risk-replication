# Cassandra-Risk closest-public replication

## Summary

This run uses Yahoo Finance SPY prices, recovered Manifold market histories where possible, and paper-based manual reconstructions where the paper does not publish historical event-series data.

## Portfolio metrics

| Metric | Buy & Hold | Vol Target | Cassandra |
| --- | ---: | ---: | ---: |
| cagr | 13.99% | 11.46% | 15.99% |
| total_return | 92.73% | 72.22% | 110.31% |
| volatility | 20.97% | 12.09% | 14.43% |
| max_drawdown_daily | -33.72% | -15.14% | -20.27% |
| max_drawdown_monthly | -23.93% | -14.78% | -19.67% |
| downside_deviation | 15.13% | 8.80% | 10.06% |
| cvar_95 | -3.18% | -1.81% | -2.12% |
| sharpe | 0.730 | 0.958 | 1.101 |
| sortino | 0.733 | 0.836 | 1.159 |
| calmar | 0.415 | 0.757 | 0.789 |
| avg_position | 100.00% | 77.29% | 78.72% |
| days_in_90pct_cash | 0 | 0 | 5 |
| max_consecutive_cash_days | 0 | 0 | 4 |

## Paper comparison

| Strategy | Metric | Reconstructed | Paper | Delta |
| --- | --- | ---: | ---: | ---: |
| buy_hold | cagr | 13.99% | 12.30% | 1.69% |
| buy_hold | total_return | 92.73% | 78.20% | 14.53% |
| buy_hold | volatility | 20.97% | 18.20% | 2.77% |
| buy_hold | max_drawdown_daily | -33.72% | n/a | n/a |
| buy_hold | max_drawdown_monthly | -23.93% | -25.40% | 1.47% |
| buy_hold | downside_deviation | 15.13% | 13.10% | 2.03% |
| buy_hold | cvar_95 | -3.18% | -3.20% | 0.02% |
| buy_hold | sharpe | 0.730 | 0.450 | 0.280 |
| buy_hold | sortino | 0.733 | 0.610 | 0.123 |
| buy_hold | calmar | 0.415 | 0.480 | -0.065 |
| buy_hold | avg_position | 100.00% | 100.00% | 0.00% |
| buy_hold | days_in_90pct_cash | 0 | 0 | 0.0 |
| buy_hold | max_consecutive_cash_days | 0 | 0 | 0.0 |
| vol_target | cagr | 11.46% | 10.10% | 1.36% |
| vol_target | total_return | 72.22% | 61.50% | 10.72% |
| vol_target | volatility | 12.09% | 12.50% | -0.41% |
| vol_target | max_drawdown_daily | -15.14% | n/a | n/a |
| vol_target | max_drawdown_monthly | -14.78% | -18.20% | 3.42% |
| vol_target | downside_deviation | 8.80% | 9.20% | -0.40% |
| vol_target | cvar_95 | -1.81% | -2.10% | 0.29% |
| vol_target | sharpe | 0.958 | 0.520 | 0.438 |
| vol_target | sortino | 0.836 | 0.740 | 0.096 |
| vol_target | calmar | 0.757 | 0.550 | 0.207 |
| vol_target | avg_position | 77.29% | 82.00% | -4.71% |
| vol_target | days_in_90pct_cash | 0 | 12 | -12.0 |
| vol_target | max_consecutive_cash_days | 0 | 31 | -31.0 |
| cassandra | cagr | 15.99% | 10.90% | 5.09% |
| cassandra | total_return | 110.31% | 67.30% | 43.01% |
| cassandra | volatility | 14.43% | 14.80% | -0.37% |
| cassandra | max_drawdown_daily | -20.27% | n/a | n/a |
| cassandra | max_drawdown_monthly | -19.67% | -14.10% | -5.57% |
| cassandra | downside_deviation | 10.06% | 8.70% | 1.36% |
| cassandra | cvar_95 | -2.12% | -1.80% | -0.32% |
| cassandra | sharpe | 1.101 | 0.680 | 0.421 |
| cassandra | sortino | 1.159 | 0.920 | 0.239 |
| cassandra | calmar | 0.789 | 0.770 | 0.019 |
| cassandra | avg_position | 78.72% | 73.00% | 5.72% |
| cassandra | days_in_90pct_cash | 5 | 48 | -43.0 |
| cassandra | max_consecutive_cash_days | 4 | 57 | -53.0 |
| cassandra | paranoia_tax | 0.020 | -0.012 | 0.032 |

## Robustness view

| Scenario | CAGR | Max Drawdown | Sortino | Avg Position |
| --- | ---: | ---: | ---: | ---: |
| lower_hazard | 15.87% | -20.51% | 1.142 | 78.82% |
| base | 15.99% | -20.27% | 1.159 | 78.72% |
| higher_hazard | 16.09% | -20.08% | 1.172 | 78.68% |

## Bootstrap confidence intervals

| Strategy | Metric | 95% CI Low | 95% CI High |
| --- | --- | ---: | ---: |
| buy_hold | cagr | -3.89% | 34.46% |
| buy_hold | max_drawdown | -0.557 | -0.138 |
| buy_hold | sharpe | -0.045 | 1.719 |
| buy_hold | sortino | -0.295 | 2.224 |
| buy_hold | cvar_95 | -4.36% | -2.30% |
| vol_target | cagr | 1.31% | 23.25% |
| vol_target | max_drawdown | -0.299 | -0.091 |
| vol_target | sharpe | 0.167 | 1.876 |
| vol_target | sortino | -0.226 | 2.174 |
| vol_target | cvar_95 | -2.04% | -1.59% |
| cassandra | cagr | 4.37% | 30.19% |
| cassandra | max_drawdown | -0.293 | -0.099 |
| cassandra | sharpe | 0.362 | 1.932 |
| cassandra | sortino | 0.108 | 2.460 |
| cassandra | cvar_95 | -2.43% | -1.80% |

## Brier score summary

| Forecast source | Mean Brier score | Sample size |
| --- | ---: | ---: |
| naive_50_50 | 0.250 | 9 |
| cassandra_aggregated | 0.642 | 9 |
| manifold | 0.498 | 4 |
| manual | 0.757 | 5 |

## Event-by-event analysis

| Event | Bucket | Peak Prob | RSI Low | Position Cut | SPY 5D Drawdown | Cassandra Avoided |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| aug_volatility_2024 | drawdown | 25.00% | 46.08% | -53.92% | 3.07% | 1.53% |
| china_taiwan_2024 | false_positive | 4.53% | 46.08% | -53.92% | 3.07% | 1.53% |
| china_taiwan_2024 | false_positive | 4.53% | 46.08% | -53.92% | 3.07% | 1.53% |
| eu_banking_contagion_2024 | false_positive | 29.00% | 27.46% | -72.54% | 1.67% | 1.04% |
| oct_selloff_2023 | drawdown | 84.73% | 18.22% | -81.78% | 5.85% | 2.17% |
| oct_selloff_2023 | drawdown | 84.73% | 18.22% | -81.78% | 5.85% | 2.17% |
| svb_contagion_2023 | drawdown | 42.00% | 23.11% | -76.89% | 1.44% | 1.06% |
| ukraine_invasion_2022 | drawdown | 98.24% | 9.27% | -90.73% | 1.73% | 1.99% |
| us_debt_ceiling_2023 | false_positive | 99.34% | 9.51% | -90.49% | 2.08% | 1.93% |
| us_debt_ceiling_2023 | false_positive | 99.34% | 9.51% | -90.49% | 2.08% | 1.93% |

## Replication gaps

- The curated Manifold shortlist currently contains 7 approved markets and replaces 4 paper/manual event definitions in the backtest event panel.
- The shortlist is semi-automatic rather than fully automatic: discovery and scoring are systematic, but approval still happens through checked-in curated review files.
- 5 event definitions still come directly from paper/manual seeds because they do not yet have an approved curated Manifold replacement.
- Catalog review decisions remain deterministic and auditable through the curated shortlist and override files, with no LLM dependency in the selection loop.
- The paper's full production event universe remains unpublished, so even the improved public Manifold pipeline still approximates, rather than exactly reproduces, the live Cassandra framework.
