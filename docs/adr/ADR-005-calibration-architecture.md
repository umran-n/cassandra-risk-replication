# ADR-005: Calibration Architecture - Current Best Stack

**Status:** Accepted  
**Date:** 2026-03-26  
**Commit:** 8ec3f50 / v0.5.7-geo-subbucket-calibration

## Context

V5 expansion to 38 events introduced a monetary concentration problem.
Three calibration approaches were tested across v0.5.2-v0.5.7.
Key empirical finding: calibration benefit is contingent on
(1) empirically-derived gap constants and (2) structural event homogeneity.

## Decision

**Monetary policy:** Apply Becker 0.0017 correction + top-5 removal + 30% cap.
- Gap is empirically derived (Kalshi, 72.1M trades)
- FOMC events are structurally homogeneous (recurring, fixed-date, similar microstructure)
- Realized benefit: Sortino +4.3% (0.231 -> 0.241)

**Geopolitical:** Governed admission (500K floor, binary, macro-relevant) + 25% cap, uncalibrated.
- Flat 0.0732 correction degraded performance: -3.6% (0.330 -> 0.318)
- Sub-bucket correction degraded further: -4.2% (0.330 -> 0.316)
- Root cause: heterogeneous event structure + theoretically estimated (not empirical) gap constants
- Uncalibrated geo signal is genuine and additive: +0.007 Sortino over monetary-only stack

## Current Best Stack

| Layer | Config | Sortino | CAGR | MDD |
| --- | --- | ---: | ---: | ---: |
| V5_Becker_top5_cap_geo | Monetary Becker + geo admission | 0.330 | 7.24% | -33.72% |

## Consequences

Geo calibration intentionally deferred until horizon-adjusted empirical gap constants
are derived from Polymarket contract resolution history.
Next calibration milestone requires: sub-bucket resolution data, horizon stratification,
and empirical gap estimation per family x horizon cell.
