# Consistency levels and read policies

Updated: 2026-11-09. This document consolidates the conversation; [spec.md](spec.md) defines the proposed adapter behavior. No adapter has been implemented.

## Current target

**Read-your-own-writes (RYOW), defaulting to latest known locally while honoring the caller’s last acknowledged write.** Explicit exact-version and any-version reads are also supported by the design. Redis Software 8.x Active-Active with three primary data shards per regional instance remains the platform. Replica shards are additional.

## Four consistency levels discussed

| Level | Meaning | Redis versus adapter responsibility | Current scope |
| --- | --- | --- | --- |
| Eventual | Regional state can differ until updates converge | Active-Active provides replication and convergence | Foundation; reads without a freshness requirement are eventual |
| Read your own writes | A caller’s dependent reads reflect its acknowledged writes, or fail explicitly when unavailable | Middleware carries context; adapter validates state and waits within a deadline | Selected |
| Strict geographic | All callers share a per-session linearizable history within the geographic authority group | Requires ordered commits, safe reads, fencing, and durable recovery in addition to the adapter | Deferred |
| Strict global | Equivalent ordering across geographic groups | Requires cross-group coordination and recovery | Deferred |

These four labels describe the options discussed, not every possible consistency model. Redis’s term “strong eventual consistency” does not mean strict consistency. Optional causal ordering does not itself mean a destination has caught up. See the [Active-Active overview](https://redis.io/docs/latest/operate/rs/databases/active-active/) and [causal consistency documentation](https://redis.io/docs/latest/operate/rs/databases/active-active/causal-consistency/).

## Read policies

| Policy | Behavior | If the required state is missing |
| --- | --- | --- |
| `latest` — default | Return the local candidate if it matches or provably incorporates the caller’s required state; otherwise retrieve that required snapshot | Bounded local wait, then freshness error |
| `required` — exact version | Return only the requested immutable snapshot, such as 42 | Bounded local wait, then freshness error |
| `any` — explicit opt-in | Return the locally selected valid candidate, possibly older/newer; no required-version check | `null` if absent; infrastructure failures remain errors |

Without prior-write context, `latest` is eventual local discovery and may return `null`. Missing expected context is an error, distinct from a genuine first read. Exact reads require authenticated version context. None of the policies bypasses authorization, integrity, generation, or expiry validation. The adapter never automatically downgrades a failed latest/required request to any.

“Latest” here is the local discovery rule, not the latest completed update across the geographic group or the world. Concurrent unrelated devices do not automatically share a totally ordered revision sequence. A local hint may lag or select an incomparable candidate. The adapter must honor the carried write even then; it may return the required snapshot instead of that candidate. A future general at-least-version API or global latest discovery needs separate design.

## Device A and Device B

A writes 42 in Region A and receives context. Device B reads in Region B, where 42 has not arrived.

- B carries authenticated context for 42: default latest or explicit required must retrieve/wait for 42, or return a freshness error. Another device can receive this guarantee through authenticated context handoff; this does not require strict geographic consistency.
- B has no context and uses default latest: return locally discovered state, perhaps 41, or `null`. B cannot infer that an unpropagated 42 exists.
- B explicitly selects any: local 41 is acceptable, and absence can return `null`. This is a deliberate eventual read.
- B carries context for 42 and local 43 is available: default latest can return 43 only if its provenance proves it incorporates 42. Explicit required 42 still returns exactly 42. An unrelated numerical label 43 is insufficient proof.

For example, if another device completes a new update after 42, RYOW alone need not expose it to B. Strict geographic would require reflecting that completed update for reads beginning afterward in the group. Immediate cross-device logout/revocation likewise needs a separately defined authorization guarantee.

## Agreed scenario and strict geographic comparison

Assume A's write of 42 has completed before either read begins, B's region still has 41 or no record, and both regions belong to the same geographic group for the strict comparison. Both devices use the default `latest` policy.

| Read | Selected design: latest local + RYOW | Strict geographic alternative |
| --- | --- | --- |
| Device A reads Region A with write context | Return 42 or a proven local successor; otherwise fail explicitly | Reflect 42 or a later committed update, or fail |
| Device B reads Region B without context for 42 | Local 41 or `null` is permitted; after replication, 42 can become the local candidate | Must reflect 42 or a later committed update; stale success and an absent result caused solely by propagation lag are forbidden |
| Device B reads Region B with authenticated context for 42 | Return 42 or a proven local successor; wait locally if needed, then return freshness error at deadline | Same minimum completed-write obligation applies regardless of caller context |

The selected guarantee follows caller context. Strict geographic establishes one per-session linearizable history for all callers in the group, so B does not need A's token to observe a completed update. It requires a shared ordering and safe-read/recovery protocol beyond replication and adapter polling. A geographic write-copy barrier alone is insufficient. Regions in different geographic groups would need a separately defined cross-group guarantee; strict geographic alone does not make foreign projections current.

The user agreed to this scenario. Device B does not automatically inherit Device A's context. Default local reads can therefore remain stale for other devices; this is accepted behavior, not an implementation defect. Immediate cross-device revocation is not supplied by the selected guarantee.

## Terminology

Exact 42 means one immutable identity within its session generation/lineage. “At least 42” requires a proven ordering or incorporates relationship. Latest local uses the accepted candidate-selection rule; latest group/global needs a stronger authority. Three data shards partition storage and do not change these consistency guarantees.
