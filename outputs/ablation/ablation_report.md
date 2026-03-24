# Ablation Report

## What Held

- `top_event_removal_ukraine` kept Cassandra Sortino at 1.203, above the Vol Target baseline of 0.836.
- `top_event_removal_debt_ceiling` kept Cassandra Sortino at 1.180, above the Vol Target baseline of 0.836.
- `aggregation_max` kept Cassandra Sortino at 1.159, above the Vol Target baseline of 0.836.
- `aggregation_weighted_average` kept Cassandra Sortino at 1.155, above the Vol Target baseline of 0.836.
- `aggregation_per_family` kept Cassandra Sortino at 1.159, above the Vol Target baseline of 0.836.
- `theme_systemic_credit_only` kept Cassandra Sortino at 1.150, above the Vol Target baseline of 0.836.
- `single_proxy_china_taiwan_2024_all_combined` kept Cassandra Sortino at 1.159, above the Vol Target baseline of 0.836.
- `single_proxy_china_taiwan_2024_dominant_only` kept Cassandra Sortino at 1.175, above the Vol Target baseline of 0.836.
- `single_proxy_oct_selloff_2023_all_combined` kept Cassandra Sortino at 1.159, above the Vol Target baseline of 0.836.
- `single_proxy_oct_selloff_2023_dominant_only` kept Cassandra Sortino at 1.143, above the Vol Target baseline of 0.836.
- `single_proxy_us_debt_ceiling_2023_all_combined` kept Cassandra Sortino at 1.159, above the Vol Target baseline of 0.836.
- `single_proxy_us_debt_ceiling_2023_dominant_only` kept Cassandra Sortino at 1.159, above the Vol Target baseline of 0.836.

## What Broke

- `no_manual_events` fell to CAGR 10.30% and Sortino 0.521; dominant theme was `geopolitical`.
- `theme_geopolitical_only` fell to CAGR 11.35% and Sortino 0.584; dominant theme was `geopolitical`.
- `theme_fiscal_debt_only` fell to CAGR 13.27% and Sortino 0.692; dominant theme was `fiscal_debt`.
- `theme_electoral_only` fell to CAGR 13.99% and Sortino 0.733; dominant theme was `none`.
- `theme_trade_technology_only` fell to CAGR 14.23% and Sortino 0.750; dominant theme was `trade_technology`.

## What Surprised

- Aggregation policy mattered by 0.004 Sortino points between forced `max` and forced `weighted_average`.
- Removing manual events changed Sortino by -0.638 versus the per-family baseline, which directly quantifies public-data dependence.
- The current per-family baseline remains `aggregation_per_family` with CAGR 15.99%, Sortino 1.159, and MDD -20.27%.
- Buy & Hold and Vol Target reference Sortinos for the same window are 0.733 and 0.836, respectively.
