# Cassandra-Risk Distribution State

Date: April 2, 2026

## Purpose

This document captures the current consumer API distribution state for
Cassandra-Risk so the next session can resume from a clean, up-to-date
checkpoint.

## Current Status

The consumer API distribution layer is now mostly covered.

### Live Commercial Channels

- [RapidAPI listing](https://rapidapi.com/umran-jkXU3nEmi/api/cassandra-risk-governed-macro-fragility-signal-api)
- [Zyla listing](https://zylalabs.com/api-marketplace/other/cassandra+risk+-+governed+macro-fragility+signal+api/12289)

### Canonical Product and Infrastructure Links

- [GitHub repository](https://github.com/umran-n/cassandra-risk-replication)
- [Railway backend](https://cassandra-risk.up.railway.app)
- [Railway health](https://cassandra-risk.up.railway.app/health)

## Channel Readout

### RapidAPI

Status: `Live`

Notes:

- primary commercial marketplace
- public listing live
- public plans live
- gateway auth working
- public endpoints tested successfully

### Zyla

Status: `Live / public / moderator review path active`

Notes:

- secondary commercial marketplace
- six public endpoints mirrored and tested successfully
- pricing and quota ladder configured
- listing currently appears under category `Other`

### Postman

Status: `Configured and validated, not prioritized for public launch`

Notes:

- public collection path proved technically
- all six public requests configured and tested through Rapid-backed auth
- no direct Railway bypass used
- platform judged lower-priority than Rapid and Zyla for current go-to-market
- can be revived later as a docs/discovery surface if needed

### APILayer

Status: `Pending`

Notes:

- curated submission path
- still worth pursuing
- not yet started in execution

### APIContext / API.expert

Status: `Pending`

Notes:

- visibility / performance / directory channels
- not treated as immediate commercial listing targets

## Practical Conclusion

Cassandra now has enough live external surface area to start collecting real
traffic, user behavior, and conversion signals without needing more immediate
distribution work.

That means the next session can focus on one of:

- reviewing inbound traffic and early user behavior
- building Tier 2 / Pro endpoint depth
- reviving Postman only if the discovery value becomes worth the friction
- preparing APILayer submission materials
- advancing Fragility Alpha / on-chain validation layer research

## Recommendation For Next Session

Default next-session posture:

- keep Rapid as primary revenue channel
- keep Zyla as secondary distribution channel
- treat Postman as optional
- pursue APILayer only when ready to package a curated submission

This leaves Cassandra in a strong position:

- live
- monetized
- multi-marketplace
- research-backed
- operationally coherent
