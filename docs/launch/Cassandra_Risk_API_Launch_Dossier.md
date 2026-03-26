# Cassandra-Risk API Launch Dossier

Date: March 27, 2026

## Purpose

This document closes the first commercial launch of the Cassandra-Risk API.
It consolidates the live product links, public endpoints, pricing, research
foundation, infrastructure, launch-state checklist, and immediate next steps
into one copy-paste source for Google Docs, launch posts, and operator use.

This document intentionally excludes secrets such as:

- RapidAPI consumer keys
- backend `CASSANDRA_API_KEY`
- backend `CASSANDRA_OPERATOR_KEY`
- any private dashboard credentials

## Executive Summary

Cassandra-Risk has now crossed the full research-to-product line:

- three published research papers with DOI-stamped public records
- a public GitHub repository with code, artifacts, and archived PDFs
- a governed live signal engine deployed to Railway
- a commercial RapidAPI listing with public plans
- PayPal linked for payouts

The result is a live sellable API:

- public listing: [RapidAPI listing](https://rapidapi.com/umran-jkXU3nEmi/api/cassandra-risk-governed-macro-fragility-signal-api)
- canonical repo: [GitHub repository](https://github.com/umran-n/cassandra-risk-replication)
- live backend domain: [Railway backend](https://cassandra-risk.up.railway.app)
- health check: [Railway health](https://cassandra-risk.up.railway.app/health)

## Public Product Definition

### Product Name

`Cassandra-Risk: Governed Macro-Fragility Signal API`

### Positioning

Cassandra-Risk is a governed macro-fragility signal API that transforms
event-implied risk from prediction markets into a live Regime Stress Index
(RSI) and an auditable event-family signal book.

### Target Users

- allocators
- macro traders
- quantitative researchers
- portfolio-risk teams
- discretionary overlay users
- dashboard builders
- research platforms

### Core Promise

Instead of waiting for realized volatility or drawdown to fully reveal
fragility, Cassandra-Risk exposes a forward-looking event-driven overlay with:

- live RSI
- governed event-family snapshots
- governed signal registry visibility
- source-status monitoring

## Live Public Links

### Marketplace and Product Links

- [RapidAPI public listing](https://rapidapi.com/umran-jkXU3nEmi/api/cassandra-risk-governed-macro-fragility-signal-api)
- [GitHub repository](https://github.com/umran-n/cassandra-risk-replication)

### Live Backend Links

These are infrastructure/operator links, not the canonical commercial entry
point for customers:

- [Railway backend root](https://cassandra-risk.up.railway.app)
- [Railway health check](https://cassandra-risk.up.railway.app/health)

### Research Links

- Paper 1 DOI: [10.13140/RG.2.2.21272.05124](https://doi.org/10.13140/RG.2.2.21272.05124)
- Paper 2 DOI: [10.13140/RG.2.2.17209.12644](https://doi.org/10.13140/RG.2.2.17209.12644)
- Paper 3 DOI: [10.13140/RG.2.2.22910.75848](https://doi.org/10.13140/RG.2.2.22910.75848)

## Public API Surface

The public Tier 1 surface currently exposed through RapidAPI is:

- `GET /v1/meta`
- `GET /v1/registry/governed`
- `GET /v1/rsi/latest`
- `GET /v1/signals/latest`
- `GET /v1/signals/latest/{event_family_id}`
- `GET /v1/sources/status`

### Canonical Rapid Base URL

```text
https://cassandra-risk-governed-macro-fragility-signal-api.p.rapidapi.com
```

### Canonical Backend Base URL

```text
https://cassandra-risk.up.railway.app
```

## Public Plan Structure

### BASIC

- price: `$0/month`
- requests: `10/month`
- limit type: `Hard Limit`
- overages: `$0`
- purpose: product evaluation / sandbox trial

### PRO

- price: `$49/month`
- requests: `10,000/month`
- plan type: `Monthly Subscription`
- plan-level rate limit: `100/minute`
- limit type: `Hard Limit`
- overages: `$0`
- status: `Recommended Plan`

### Plans Not Launched

- `ULTRA`: off
- `MEGA`: off

## Launch-State Checklist

### Product and Research

- [x] Paper 1 published
- [x] Paper 2 published
- [x] Paper 3 published
- [x] PDFs archived in repo
- [x] `CITATION.cff` added to repo

### Code and Infrastructure

- [x] unified signal API built
- [x] governed promotion workflow built
- [x] market-ready auth and rate limiting added
- [x] deploy-ready scaffold pushed
- [x] Railway deployment live
- [x] health check passing

### Marketplace

- [x] RapidAPI project created
- [x] public listing configured
- [x] six public endpoints defined
- [x] gateway secret header configured
- [x] all public endpoints tested successfully through Rapid
- [x] public plans configured
- [x] PayPal payouts linked

## Infrastructure and Moving Parts

### High-Level Flow

```text
GitHub repo
  -> Railway deployment
  -> RapidAPI gateway
  -> End users / subscribers
```

### Internal Runtime Flow

```text
Prediction market sources
  -> source adapters
  -> governed registry and promotion workflow
  -> live signal snapshots
  -> RSI engine
  -> Railway backend
  -> RapidAPI public listing
```

### Source Layer

Phase 6 source foundation covers:

- Polymarket
- Kalshi
- Metaculus
- Manifold

### Governance Layer

- governed registry stored in `data/governed/signal_registry.json`
- promotion audit stored in `data/governed/promotion_audit.json`
- operator review path in `scripts/review_queue.py`
- public and operator routes separated in the API surface

### Authentication Model

- end users authenticate through RapidAPI
- Rapid injects hidden upstream `X-API-Key` to the Railway backend
- operator routes remain off-marketplace and require operator auth

## Launch Snapshot

The live snapshot at launch from `outputs/signals/rsi_snapshot.json` is:

- as of: `2026-03-26`
- RSI: `0.09873728734627346`
- total hazard: `9.127886099331267`
- active event count: `3`
- dominant theme: `geopolitical`
- dominant event family:
  `geopolitical_another_israeli_military_action_against_iran_in_2024_2025`

### Active Governed Signals at Launch

1. `geopolitical_another_israeli_military_action_against_iran_in_2024_2025`
   - source: `polymarket`
   - market id: `1551490`
   - governed probability: `0.88`
   - calibration: `none`

2. `monetary_policy_fed_emergency_rate_cut_in_2024_2025`
   - source: `polymarket`
   - market id: `616903`
   - governed probability: `0.26`
   - calibration: `becker`

3. `geopolitical_russia_x_ukraine_ceasefire_in_2024_2025`
   - source: `polymarket`
   - market id: `561829`
   - governed probability: `0.005`
   - calibration: `none`

## Papers and Research Foundation

### Paper 1

`Beyond Value-at-Risk: Quantifying Regime Fragility via Prediction Market Event Forecasting`

- DOI: [10.13140/RG.2.2.21272.05124](https://doi.org/10.13140/RG.2.2.21272.05124)

### Paper 2

`Cassandra-Risk Paper 2: Beyond the Backtest - Expansion, Calibration, and the Boundary Conditions of Forecast-Based Risk Overlays`

- DOI: [10.13140/RG.2.2.17209.12644](https://doi.org/10.13140/RG.2.2.17209.12644)

### Paper 3

`Cassandra-Risk Paper 3: Cross-Platform Prediction Market Ensembles and Governed Signal Infrastructure`

- DOI: [10.13140/RG.2.2.22910.75848](https://doi.org/10.13140/RG.2.2.22910.75848)

## Key Build Milestones

Selected Phase 6 and launch milestones:

- `d613de5` - Phase 6 unified signal API foundation
- `4cb7f16` - live refresh and query endpoints
- `8b7331a` - governed promotion workflow
- `bf6325a` - explicit aggregation policy and deterministic family selection
- `407f472` - market-ready API hardening
- `9e9e90c` - deploy-ready scaffold for Railway and Render

## Files and System Components

### Key Repo Paths

- [README.md](C:/Users/Admin/.codex/worktrees/f146/New%20project/README.md)
- [api/app.py](C:/Users/Admin/.codex/worktrees/f146/New%20project/api/app.py)
- [Dockerfile](C:/Users/Admin/.codex/worktrees/f146/New%20project/Dockerfile)
- [source_registry.json](C:/Users/Admin/.codex/worktrees/f146/New%20project/config/source_registry.json)
- [signal_registry.json](C:/Users/Admin/.codex/worktrees/f146/New%20project/data/governed/signal_registry.json)
- [promotion_audit.json](C:/Users/Admin/.codex/worktrees/f146/New%20project/data/governed/promotion_audit.json)
- [rsi_snapshot.json](C:/Users/Admin/.codex/worktrees/f146/New%20project/outputs/signals/rsi_snapshot.json)
- [Paper 2 manuscript](C:/Users/Admin/.codex/worktrees/f146/New%20project/paper/Cassandra_Risk_Paper_2_SSRN_Ready.md)
- [Paper 3 manuscript](C:/Users/Admin/.codex/worktrees/f146/New%20project/paper/Cassandra_Risk_Paper_3_SSRN_Ready.md)

### Archived Paper PDFs

- [Paper 1 PDF](C:/Users/Admin/.codex/worktrees/f146/New%20project/paper/pdfs/Beyond%20Value-at-Risk_%20Quantifying%20Regime%20Fragility%20via%20Prediction%20Market%20Event%20Forecasting.pdf)
- [Paper 2 PDF](C:/Users/Admin/.codex/worktrees/f146/New%20project/paper/pdfs/Cassandra-Risk%20Paper%202%20Beyond%20the%20Backtest%20-%20Expansion,%20Calibration,%20and%20the%20Boundary%20Conditions%20of%20Forecast-Based%20Risk%20Overlays.pdf)
- [Paper 3 PDF](C:/Users/Admin/.codex/worktrees/f146/New%20project/paper/pdfs/Cassandra-Risk%20Paper%203%20Cross-Platform%20Prediction%20Market%20Ensembles%20and%20Governed%20Signal%20Infrastructure.pdf)

## Access Notes

### Share Publicly

- RapidAPI listing URL
- GitHub repo URL
- DOI links
- product screenshots
- public endpoint examples through RapidAPI

### Keep Internal

- Railway dashboard controls
- backend environment variables
- operator key
- any direct operator-only endpoint workflow
- any unpublished future routes

### Canonical Public Entry Point

The canonical customer-facing entry point should be the RapidAPI listing, not the
raw Railway backend URL.

## Immediate GTM Plan

### Day 1 Objectives

- publish the launch on LinkedIn
- publish the launch on X / Twitter
- add the RapidAPI listing URL to the repo README if desired
- add the RapidAPI listing URL to paper distribution posts
- message a small set of first potential users directly

### Likely Early Acquisition Channels

- readers of Papers 1-3
- RapidAPI marketplace discovery
- GitHub visitors
- LinkedIn macro / quant network
- direct outreach to research and allocator contacts

## Marketplace Expansion Plan

The widest reach strategy should separate:

- marketplaces for monetization
- marketplaces/networks for discovery
- direct owned distribution

### 1. RapidAPI

Status: `Live now`

Role:

- commercial API marketplace
- subscription billing
- public discovery
- quick developer onboarding

### 2. Postman API Network

Role:

- developer discovery
- documentation distribution
- collection-based onboarding
- strong fit for public API exploration even if monetization remains elsewhere

Official docs:

- [Publish your public APIs to the Postman API Network](https://learning.postman.com/docs/postman-api-network/showcase/publish/overview/)
- [Explore and Publish to the Postman API Network](https://learning.postman.com/docs/postman-api-network/overview)

Recommended next move:

- create a public Postman workspace for Cassandra-Risk
- publish a clean collection covering the six public endpoints
- use it as a documentation and adoption channel

### 3. AWS Data Exchange for APIs

Role:

- enterprise-grade distribution
- AWS-native procurement path
- useful for institutional buyers who prefer AWS Marketplace / Data Exchange

Important architectural note:

AWS Data Exchange for APIs proxies through Amazon API Gateway. The current
Railway deployment proves the commercial product, but an AWS Data Exchange
listing would require an API Gateway-based front door or migration path.

Official docs:

- [Publishing a product in AWS Data Exchange containing APIs](https://docs.aws.amazon.com/data-exchange/latest/userguide/publish-API-product.html)
- [Publishing a new product in AWS Data Exchange](https://docs.aws.amazon.com/data-exchange/latest/userguide/publishing-products.html)

Recommended next move:

- treat AWS Data Exchange as the next enterprise channel, not the next-day task
- first validate demand via RapidAPI and direct outreach

### 4. Direct Owned Distribution

Role:

- own the narrative
- preserve margins
- support future enterprise/off-platform deals

Recommended next move:

- simple landing page
- direct documentation page
- email capture or contact form
- repo and paper links on the same page

## Exclusivity Note

I have not verified any exclusivity requirement in current RapidAPI provider
documentation during this launch process. Before listing Cassandra on additional
commercial marketplaces, review the current provider terms for:

- RapidAPI
- any future marketplace
- payout and billing terms
- plan and price-parity clauses if any exist

This should be treated as a business/legal checklist item before duplicate
commercial listings, not as an assumed green light.

## Tomorrow Checklist

1. copy this dossier into Google Docs
2. publish LinkedIn launch post
3. publish X / Twitter launch post
4. share the RapidAPI listing URL
5. share the GitHub repo URL
6. monitor first usage and subscriptions
7. decide whether to add RapidAPI docs page content immediately
8. plan Postman API Network listing
9. plan AWS Data Exchange feasibility separately

## Closing Note

This launch matters because it is the first point at which Cassandra exists as:

- research
- code
- infrastructure
- documentation
- monetization
- public distribution

That is not a prototype milestone. It is a product milestone.
