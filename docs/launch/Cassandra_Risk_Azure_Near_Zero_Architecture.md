# Cassandra-Risk Azure Near-Zero Architecture

Date: April 13, 2026

## Purpose

This document defines the lowest-cost Azure architecture that keeps
Cassandra-Risk available as a transactable enterprise SaaS offer while there
are zero or near-zero customers.

The goal is not maximum performance. The goal is:

- valid Microsoft Marketplace SaaS architecture
- minimal idle spend
- fast enough activation path when a real buyer lands
- reusable commerce rail for future Cassandra products

## Core Principle

Consumer Cassandra and Enterprise Cassandra should be treated as different
deployment surfaces:

- Consumer/self-serve: Railway + RapidAPI + Zyla
- Enterprise: Azure-hosted SaaS wrapper and Azure-hosted Enterprise Tier 1 API

This keeps the public API lightweight while making the enterprise listing
credible for Azure procurement and certification review.

## Target Product Framing

Enterprise Cassandra on Azure is not the public V4 proof-of-concept product.
It is the Enterprise Tier 1 production signal:

- governed V5 universe
- top-5 removal
- 30% bucket cap
- Becker calibration
- geopolitical adjustment
- asymmetric Kelly internal weighting

Client message:

> Paper 1 is the proof of concept. Enterprise Tier 1 is the production signal.

## Near-Zero Architecture

### 1. Landing Page

Service:

- Azure Static Web Apps

Purpose:

- Microsoft Marketplace post-purchase landing page
- sign-in handoff
- activation UI
- enterprise onboarding screen

Why:

- low idle cost
- easy HTTPS hosting
- sufficient for a lightweight purchase-resolution frontend

### 2. SaaS Fulfillment + Webhook Layer

Service:

- Azure Functions (Consumption plan)

Purpose:

- connection webhook endpoint for Marketplace events
- token resolution / activation handler
- plan change / suspend / cancel handlers
- enterprise key provisioning trigger

Why:

- pay-per-use
- good fit for event-driven fulfillment logic
- low cost at zero or low traffic

### 3. Enterprise API Runtime

Service:

- Azure Container Apps (Consumption)

Purpose:

- host Enterprise Tier 1 Cassandra API
- expose private enterprise routes and enterprise auth layer
- scale to zero when unused

Why:

- closest fit to the existing FastAPI service
- supports containerized deployment cleanly
- idle cost can stay near zero when no requests are coming in

### 4. Subscription / Tenant State

Service options:

- Azure Table Storage
- or Azure Storage account with minimal table/blob usage

Purpose:

- marketplace subscription ID to Cassandra tenant mapping
- offer / plan metadata
- enterprise key issuance state
- activation timestamps and account status

Why:

- extremely cheap at low volume
- enough for a first marketplace control plane

### 5. Secrets

Service:

- Azure Key Vault

Purpose:

- Marketplace credentials
- enterprise signing keys
- operator secrets
- downstream API credentials if needed

Why:

- keeps the enterprise control plane production-safe
- low spend at small scale

## Runtime Flow

### Purchase Flow

1. Buyer purchases Cassandra-Risk Enterprise on Azure Marketplace.
2. Buyer lands on the Azure-hosted Cassandra landing page.
3. Landing page resolves the purchase token through the fulfillment backend.
4. Backend creates or links a Cassandra enterprise tenant.
5. Enterprise API key is issued.
6. Buyer receives activation confirmation and onboarding instructions.

### Lifecycle Flow

1. Microsoft sends subscription event to webhook.
2. Azure Function validates event and reads tenant mapping.
3. Tenant status is updated:
   - active
   - suspended
   - canceled
   - changed plan
4. Enterprise access is updated in Cassandra control state.

## Cost Philosophy

The design target is:

- no Marketplace listing fee
- only minimal Azure infrastructure spend while idle

Expected idle-cost posture:

- Static Web Apps: near-zero or free-tier eligible
- Azure Functions Consumption: near-zero at low invocation counts
- Container Apps Consumption: near-zero if scaled to zero
- Storage + Key Vault: small recurring operational cost

Operational interpretation:

- the enterprise listing can stay "on the shelf"
- real cost should begin scaling only when buyers arrive

## What Is Deliberately Not Included Yet

To keep the first Azure version lean, do not add:

- always-on VM infrastructure
- managed Kubernetes
- complex analytics warehouse dependencies
- heavy observability stack by default
- multi-region failover
- enterprise SSO beyond the required Marketplace and Microsoft identity flow

These can be added after the first paying enterprise customers appear.

## Minimum Build Scope

The first Azure SaaS implementation should include only:

- one landing page
- one webhook / fulfillment function app
- one enterprise API container app
- one minimal subscription-state store
- one secrets store

Everything else is optional until customer demand justifies it.

## Architecture Decision

Near-zero Azure is the default enterprise-marketplace posture for Cassandra.

Rules:

- do not host Enterprise Cassandra on Railway for Azure Marketplace
- keep consumer and enterprise deployment surfaces separate
- prefer scale-to-zero services until enterprise demand exists
- price enterprise offers high enough to absorb Azure infra and support costs

## Reuse Value

This architecture should be built as a reusable enterprise commerce rail, not
as a one-off Cassandra listing implementation.

After the first build, the same Azure pattern can be reused for:

- Cassandra-Risk Enterprise Tier 1
- Fragility Alpha
- future enterprise-only layers
- future marketplace-facing Cassandra products

## Next Build When Azure Execution Starts

1. Create Azure Marketplace publisher account under LLP.
2. Choose transactable SaaS offer type.
3. Build Azure landing page.
4. Build fulfillment / webhook Functions app.
5. Containerize and deploy Enterprise Cassandra to Azure Container Apps.
6. Add tenant and subscription mapping store.
7. Connect Marketplace purchase flow to enterprise key issuance.
8. Dry-run end-to-end activation before offer submission.
