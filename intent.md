# Intent: multi-region session consistency

Date: 2026-11-09. Status: consistency target agreed; detailed design proposed.

## Problem and outcome

A session request can move regions before its last update has propagated. The destination may hold older state or no record. Provide an in-process adapter that preserves the caller's acknowledged state without business-code polling or version comparisons.

The selected contract is **Session (RYOW)**. The default read can use a later locally known snapshot only when its history proves it succeeds the caller's write. Otherwise it retrieves the required snapshot or reports it as missing after bounded waiting. Available reads are an explicit option. Expected versions and exact-snapshot lookup stay internal to Session enforcement.

**Session (RYOW)**, named `session`, is the default public read behavior. It does not imply full causal consistency. **Available**, named `available`, is the explicit alternative; exact-version selection is internal plumbing, not a public policy.

Convergence, read consistency, and cluster-group scope are distinct. Explicit `available` has no freshness guarantee; default `session` enforces RYOW when protected caller context is present. Linearizability would require shared per-session ordering for all callers in a selected scope. “Linearizable geographic” and “linearizable global” mean geographic-group and all-region scopes of that same deferred guarantee. Group membership alone does not enforce linearizability, restrict RYOW movement, or change acknowledgment participants. Linearizable scopes are explanatory concepts, not supported read-policy settings.

## Agreed regional clients

A1 and A2 both read and write in `us-west-2`. B1 reads/writes in `us-east-1`; C1 in `us-east-2`; D1 in `eu-west-1`; E1 in `eu-central-1`. The three US regions form the US group; the two EU regions form the EU group. All clients are independent and do not exchange write context, version IDs, notifications, or shared latest-version metadata. Redis replication or adapter fan-out still transports session data.

A1's acknowledged write of 42 protects A1's own dependent reads. A2 may discover it through the shared regional Redis database after candidate publication, with no WAN hop, but same-region placement does not transfer A1's context or guarantee cross-client latest state. B1/C1/D1/E1 can read older local state or null until data arrives and is selected locally. Each client's own writes establish its separate RYOW requirement.

The example assumes A1/A2 use the same logical regional Redis database; confirm endpoint/cell layout before implementation. Defaults remain Session (RYOW) with local acknowledgment as baseline and independent recovery explicitly selected. See [consistency.md](consistency.md).

## Platform and delivery choices

Use Redis Software 8.x with three primary data shards per regional database, plus separately sized replicas. Offer Active-Active or independent regional databases with adapter-managed fan-out. No fixed session home cluster or request-path session service is required.

Groups describe geographic membership, not a new consistency default or an implicit acknowledgment barrier. Under local acknowledgment, distribution to the foreign group remains asynchronous. Independent mode supports local or all-target acknowledgment, separately from request-only or durable-replay recovery. Request-only sends the next insert/update's latest version; it does not require manual repair or preserve every historical version. Durable replay is optional and can finish saved delivery work without a new write.

Reference geography is US (`us-east-1`, `us-east-2`, `us-west-2`) and EU (`eu-west-1`, `eu-central-1`). Membership is configurable. Cells are application deployment units and do not automatically correspond to Redis databases.

## Users, constraints, and success

Developers integrate the adapter, platform engineers operate transport and databases, and service/security owners set durability, expiry, and authorization policies. Middleware propagates protected context for the same caller across cells and regions. There is no automatic remote read fallback or silent downgrade to stale reads.

Pass the applicable scenarios in [validation.md](validation.md), with measured targets agreed before production acceptance. Distinguish snapshot missing, ordinary eventual absence, explicit expiry, and infrastructure failure. Exclude payloads, credentials, bearer IDs, and raw context from telemetry.

Linearizable geographic/global ordering, general cross-device latest-state discovery, cross-session transactions, and immediate cross-device revocation are outside this phase. Authorization requiring those guarantees needs a separate design. Resolve the open decisions in [sources.md](sources.md) before implementation; the user's consistency selection does not approve every proposed mechanism.
