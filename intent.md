# Intent: multi-region session consistency

Date: 2026-11-09. Status: consistency target agreed; detailed design proposed.

## Problem and outcome

A session request can move regions before its last update has propagated. The destination may hold older state or no record. Provide an in-process adapter that preserves the caller's acknowledged state without business-code polling or version comparisons.

The selected contract is **latest local with read-your-own-writes (RYOW)**. The default read can use a later locally known snapshot only when its history proves it succeeds the caller's write. Otherwise it retrieves the required snapshot or reports it as missing after bounded waiting. Exact-version and any-version reads are explicit options.

## Agreed Device A/B scenario

A writes 42 in Region A and receives context. A's subsequent local read returns 42 or a proven successor. B in Region B without that context may see 41 or `null`. With authenticated context transferred to B, its default read must return 42/a proven successor or a freshness error described as **snapshot missing**.

This is not strict geographic consistency: B without context need not see another device's completed update. The guarantee follows caller context. Detailed examples live in [consistency.md](consistency.md).

## Platform and delivery choices

Use Redis Software 8.x with three primary data shards per regional database, plus separately sized replicas. Offer Active-Active or independent regional databases with adapter-managed fan-out. No fixed session home cluster or request-path session service is required.

Independent mode supports local or all-target acknowledgment, separately from request-only or durable-replay recovery. Request-only sends the next insert/update's latest version; it does not require manual repair or preserve every historical version. Durable replay is optional and can finish saved delivery work without a new write.

Reference geography is US (`us-east-1`, `us-east-2`, `us-west-2`) and EU (`eu-west-1`, `eu-central-1`). Membership is configurable. Cells are application deployment units and do not automatically correspond to Redis databases.

## Users, constraints, and success

Developers integrate the adapter, platform engineers operate transport and databases, and service/security owners set durability, expiry, and authorization policies. Middleware propagates protected context across cells, regions, and authorized device handoffs. There is no automatic remote read fallback or silent downgrade to stale reads.

Pass the applicable scenarios in [validation.md](validation.md), with measured targets agreed before production acceptance. Distinguish snapshot missing, ordinary eventual absence, explicit expiry, and infrastructure failure. Exclude payloads, credentials, bearer IDs, and raw context from telemetry.

Strict geographic/global ordering, general cross-device latest-state discovery, cross-session transactions, and immediate cross-device revocation are outside this phase. Authorization requiring those guarantees needs a separate design. Resolve the open decisions in [sources.md](sources.md) before implementation; the user's consistency selection does not approve every proposed mechanism.
