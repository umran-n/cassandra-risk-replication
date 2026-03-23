# Cassandra-Risk closest-public replication

## Summary

This run uses Yahoo Finance SPY prices, recovered Manifold market histories where possible, and paper-based manual reconstructions where the paper does not publish historical event-series data.

## Portfolio metrics

| Metric | Buy & Hold | Vol Target | Cassandra |
| --- | ---: | ---: | ---: |
| cagr | 13.99% | 11.46% | 17.84% |
| total_return | 92.73% | 72.22% | 127.71% |
| volatility | 20.97% | 12.09% | 14.77% |
| max_drawdown_daily | -33.72% | -15.14% | -20.27% |
| max_drawdown_monthly | -23.93% | -14.78% | -19.67% |
| downside_deviation | 15.13% | 8.80% | 10.26% |
| cvar_95 | -3.18% | -1.81% | -2.13% |
| sharpe | 0.730 | 0.958 | 1.186 |
| sortino | 0.733 | 0.836 | 1.296 |
| calmar | 0.415 | 0.757 | 0.880 |
| avg_position | 100.00% | 77.29% | 84.09% |
| days_in_90pct_cash | 0 | 0 | 1 |
| max_consecutive_cash_days | 0 | 0 | 1 |

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
| cassandra | cagr | 17.84% | 10.90% | 6.94% |
| cassandra | total_return | 127.71% | 67.30% | 60.41% |
| cassandra | volatility | 14.77% | 14.80% | -0.03% |
| cassandra | max_drawdown_daily | -20.27% | n/a | n/a |
| cassandra | max_drawdown_monthly | -19.67% | -14.10% | -5.57% |
| cassandra | downside_deviation | 10.26% | 8.70% | 1.56% |
| cassandra | cvar_95 | -2.13% | -1.80% | -0.33% |
| cassandra | sharpe | 1.186 | 0.680 | 0.506 |
| cassandra | sortino | 1.296 | 0.920 | 0.376 |
| cassandra | calmar | 0.880 | 0.770 | 0.110 |
| cassandra | avg_position | 84.09% | 73.00% | 11.09% |
| cassandra | days_in_90pct_cash | 1 | 48 | -47.0 |
| cassandra | max_consecutive_cash_days | 1 | 57 | -56.0 |
| cassandra | paranoia_tax | 0.039 | -0.012 | 0.051 |

## Robustness view

| Scenario | CAGR | Max Drawdown | Sortino | Avg Position |
| --- | ---: | ---: | ---: | ---: |
| lower_hazard | 17.77% | -20.51% | 1.282 | 84.68% |
| base | 17.84% | -20.27% | 1.296 | 84.09% |
| higher_hazard | 17.91% | -20.08% | 1.307 | 83.65% |

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
| cassandra | cagr | 5.60% | 32.97% |
| cassandra | max_drawdown | -0.294 | -0.102 |
| cassandra | sharpe | 0.437 | 2.038 |
| cassandra | sortino | 0.215 | 2.652 |
| cassandra | cvar_95 | -2.43% | -1.83% |

## Brier score summary

| Forecast source | Mean Brier score | Sample size |
| --- | ---: | ---: |
| naive_50_50 | 0.250 | 9 |
| cassandra_aggregated | 0.421 | 9 |
| manifold | 0.000 | 4 |
| manual | 0.757 | 5 |

## Event-by-event analysis

| Event | Bucket | Peak Prob | RSI Low | Position Cut | SPY 5D Drawdown | Cassandra Avoided |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| ukraine_invasion_2022 | drawdown | 98.24% | 9.27% | -90.73% | 1.73% | 1.99% |
| svb_contagion_2023 | drawdown | 42.00% | 23.11% | -76.89% | 1.44% | 1.06% |
| us_debt_ceiling_2023 | false_positive | 48.14% | 21.11% | -78.89% | 2.08% | 0.12% |
| oct_selloff_2023 | drawdown | 84.73% | 19.53% | -80.47% | 5.85% | 0.00% |
| china_taiwan_2024 | false_positive | 4.53% | 46.08% | -53.92% | 3.07% | 1.53% |
| aug_volatility_2024 | drawdown | 25.00% | 46.08% | -53.92% | 3.07% | 1.53% |
| eu_banking_contagion_2024 | false_positive | 29.00% | 27.46% | -72.54% | 1.67% | 1.04% |

## Replication gaps

- V3 searched all nine kill-list events through Manifold and upgraded 2 manual reconstructions to public market histories, but several events still have no clean public market coverage.
- 1 candidate markets were intentionally rejected because they were created only after the target event window had already started, which would otherwise introduce look-ahead bias.
- The 2020 COVID crash and the mid-2022 rate-hike shock remain manually reconstructed because public Manifold coverage for those windows was not recoverable via search.
- 2 kill-list events returned no usable Manifold match at all, and another 2 returned search hits that were judged too weak or off-target to replace the manual series.
- Even with broader Manifold coverage, the paper's full historical event panel remains unpublished, so the public replication can only approximate the production Cassandra signal rather than exactly reproduce it.
