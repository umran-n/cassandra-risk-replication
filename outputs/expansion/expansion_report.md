# Expansion Backtest Report

## Scope

- `V4` baseline uses the original 9-event governed universe.
- `V5` uses `data/curated/polymarket_approved.json` as the 38-event approved universe.
- Active historical loads from the approved universe: `32`
- Approved entries skipped for lack of history: `6`

## Summary Table

| Version | n_events | Cassandra Sortino | Cassandra CAGR | Cassandra Daily MDD | Cassandra Avg Position | Vol Target Sortino |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V4 | 9 | 1.159 | 15.99% | -20.27% | 78.72% | 0.836 |
| V5 | 38 | 0.231 | 5.75% | -33.72% | 67.26% | 0.836 |

## Delta Versus V4

- Sortino delta: `-0.927`
- CAGR delta: `-10.24%`
- Daily MDD delta: `-13.45%`
- Avg position delta: `-11.46%`

## Interpretation

- The approved 38-event universe de-risks more often, but the public Polymarket-only historical panel does not convert that extra caution into better downside-adjusted performance.
- In this run, V5 underperforms both the V4 Cassandra baseline and the Vol Target benchmark on Sortino.
- The most likely causes are event-density over-warning and the fact that 6 approved Metaculus entries remain placeholders with no usable historical path in the workspace.

## Notes

- `benchmark_sortino` is the Vol Target Sortino from the same run.
- Manual Metaculus approvals remain governed-universe entries, but they do not contribute live history in this public replication because no Metaculus time series is available in the workspace yet.
