# Intent: read-your-own-writes across regions

Date: 2026-11-09

Status: RYOW target selected by repository owner; detailed design pending review

Companions: [spec.md](spec.md), [sources.md](sources.md)

## Problem

A caller updates a session in one region, then moves to another before replication arrives. The destination may have older state or no record. An ordinary eventual read can therefore fail to reflect the caller's acknowledged update.

## Desired outcome

An in-process adapter preserves read-your-own-writes across cells and regions. An acknowledged write returns both its immutable record identity and context for subsequent reads. Middleware propagates that context so a default read returns an eligible local snapshot that incorporates the caller’s write, the required snapshot itself, or an explicit failure to satisfy freshness within its deadline.

This phase chooses RYOW rather than strict geographic consistency. It does not require a read to observe another caller's later update. It does not require every geographic participant to apply a write before acknowledgment.

## Device B read options

Default to latest known locally while honoring the caller’s acknowledged write. With no prior context this is eventual local discovery. Provide an explicit per-request choice: require exact version 42 using authenticated transferred context, or accept any locally available valid version without a required-version guarantee. The any-version policy may return older/newer state or `null`, has no freshness wait, and must not overwrite protected caller context. Required-version timeout remains an error with no automatic downgrade. Exact 42 is distinct from a future “42 or later” policy.

## Agreed default scenario

After A writes 42 in Region A, A's local read carries its context and returns 42 or a proven successor. B's read in Region B without that context may return local 41 or `null` until replication catches up. If context is transferred to B through authenticated handoff, B waits for 42 or returns a freshness error; default reads can also return a proven local successor. This behavior was explicitly agreed by the user. Unlike strict geographic consistency, the selected design does not automatically protect every device against another device's completed but unpropagated update.

## Platform and users

Use Redis Software 8.x Active-Active, with three primary data shards per regional database instance; replicas are additional. Developers integrate the adapter, platform engineers operate Redis, and service owners define latency, persistence, expiry, and security requirements.

Reference groups are US (`us-east-1`, `us-east-2`, `us-west-2`) and EU (`eu-west-1`, `eu-central-1`). Membership is configurable. Cells are application deployment units, not automatically Redis participants. Context follows the caller even across geographic groups; replication remains asynchronous.

## Constraints

- No fixed session home cluster. A read waits at its selected endpoint; there is no automatic remote fallback in the initial proposal.
- No business-code version checks or replication polling.
- Carry context on every protected read. Missing or invalid required context cannot silently downgrade the operation to eventual consistency.
- An expected unexpired snapshot that has not arrived produces a freshness error after bounded waiting, not `null`.
- An unprotected exact-ID miss may return `null`; authoritative expiry of the requested record may also produce an explicit expired/absent result.
- Session payloads, credentials, bearer IDs, and raw context tokens do not enter telemetry.

## Success

Pass the scenarios in [validation.md](validation.md), including region movement, stale hits, propagation delay, retries, lost context, concurrent callers, and recovery. Agree numeric latency/throughput targets, payload sizes, retention, durability, RPO, and RTO before production acceptance.

## Boundaries and questions

Strict geographic/global ordering, cross-caller latest-state discovery, geographic all-member barriers, and immediate cross-caller revocation are deferred. Applications requiring current authorization need a separate security mechanism; RYOW alone does not provide it.

Resolve SDK language, middleware integration, token protection and storage, snapshot lifetime, ambiguous-write reconciliation, persistence, supported commands, and performance targets during detailed review. The user selected the consistency target; that selection does not imply approval of every proposed implementation detail.
