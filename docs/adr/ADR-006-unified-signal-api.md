# ADR-006: Unified Signal API Foundation

**Status:** Accepted  
**Date:** 2026-03-26  
**Commit:** v0.6.0-unified-signal-api  

## Context

By the end of Paper 2, Cassandra-Risk had a governed backtest architecture but no unified live signal plane. Source-specific logic lived in separate ingestion scripts and curated files:

- Manifold shortlist governance
- Polymarket historical dredger and approved universe
- Metaculus placeholders without live integration
- No Kalshi adapter in the repo

This made live signal collection brittle. It also made it difficult to package Cassandra as an API because the project had no canonical event graph, no source registry, and no clear separation between governed signals and autonomous discovery candidates.

## Decision

Introduce a unified signal API foundation with four layers:

1. **Source registry**
   A single config file defines source priority, auth mode, quality tier, discovery limits, and theme governance policies.

2. **Canonical event graph**
   Governed families from seeds and curated universes remain the canonical spine. Live source markets are linked into those families by explicit market ID or text similarity. High-quality unlinked markets are retained as discovered candidates rather than discarded.

3. **Signal engine**
   The engine selects one live market per governed family, applies current governance rules, and emits a canonical signal book plus a current RSI snapshot.

4. **Local API**
   A lightweight HTTP server exposes:
   - source status
   - governed family book
   - discovered candidates
   - latest governed signals
   - latest RSI snapshot

## Consequences

- Cassandra now has a governed data plane in addition to a governed backtest plane.
- Monetary-policy live signals inherit the validated Becker layer and bucket cap.
- Geopolitical discovered markets can be collected autonomously without silently entering the governed RSI.
- Metaculus can join the same fabric once API credentials or export access are available.
- Kalshi becomes a first-class source in the same registry instead of a separate future project.

## Current Boundary

This milestone does **not** solve:

- empirical Metaculus historical recovery
- horizon-adjusted geopolitical calibration
- automatic promotion of discovered candidates into the governed universe

Those remain subsequent milestones. ADR-006 only freezes the foundation that makes them composable.
