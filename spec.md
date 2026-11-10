# Specification: Local and Available reads across regions

Date: 2026-11-09. Status: revised production design; implementation proposed.

Inputs: [intent.md](intent.md), [sources.md](sources.md). Proof: [validation.md](validation.md).

## Selected contract

The public default is **Available** (`available`): concurrently query every regional cluster in the selected read group, including the local cluster, and return the first valid non-null candidate. A null reply never wins over an outstanding request that may return a value. If every cluster returns null, return null immediately. If the shared deadline expires before a valid value is obtained, return null even when some clusters have not replied.

**Local** (`local`) reads only the selected local cluster and returns its valid candidate or null. Redis Active-Active owns propagation in that backend; independent regional databases require adapter-managed write distribution. Local reads do not start regional read fan-out.

Neither behavior guarantees read-your-own-writes, monotonic reads, or the newest completed write. Different values may exist; Available returns whichever valid value arrives first without comparing versions or waiting for agreement. Null on deadline is an availability outcome, not proof of absence throughout the group.

The Session read option and its automatic context/lineage enforcement have been removed from the production plan. Record identities remain internal distribution/idempotency metadata, not a public read selector or freshness requirement. The experimental spike retains legacy controls and results; it is not this production API.

## Public read policies

| Behavior / policy | Scope | Result |
| --- | --- | --- |
| **Local** / `local` | Local cluster only | Valid local candidate or null; local infrastructure failures remain errors. |
| **Available** / `available` (default) | Every member of the selected group, including local | First valid non-null value; null if all replies are null or the deadline expires without a value. |
| **Causal (Active-Active)** / `causal` (proposed adapter integration) | A regional instance of an Active-Active database with causal consistency enabled | Preserve causal order on the same key through native replication; regional reads may still lag. Requires verified deployment configuration, not a freshness barrier. |
| **Coordinated (independent clusters)** / `coordinated` (proposed) | Independent, non-Active-Active clusters in the selected geographic/global group | Target: linearizable-like access through application coordination; exact freshness/order/failure guarantees are unselected. Unsupported; reject rather than downgrade. |
| **Linearizable** / `linearizable` (deferred) | Active-Active is required by this project's architecture, plus a geographic/global coordination protocol | Contract: real-time ordering per key. Unsupported until the additional protocol is designed and validated; Active-Active alone is insufficient. |

Resolve policy from the request override or store configuration, initially `available`. A Local or Available read still checks caller authorization, session/key binding, integrity, generation policy, and expiry. Policy selection never bypasses access checks.

## Group membership and deadlines

A1/A2 use `us-west-2`, B1 `us-east-1`, C1 `us-east-2`, D1 `eu-west-1`, and E1 `eu-central-1`. A1/A2 share one logical west regional database in this example. Five regional databases with three primary shards each mean fifteen primary shards before replicas; clients and shards are not fan-out targets.

The configured US group contains the three US regions; EU contains the two EU regions. Available uses the local region's configured read group unless the request explicitly selects another allowed group. The selected group must be nonempty, contain the local cluster, and resolve to known unique regional endpoints. An optional global group must explicitly contain all five regions. Reject unknown, empty, or malformed groups and unauthorized overrides before dispatch; never silently remove a target on timeout.

Capture group membership/configuration epoch and a shared finite read deadline once per request. Fan out to all captured members concurrently, including local, rather than trying local first and sequentially falling back. Do not contact regions outside that group. Available read groups are independent of write fan-out/acknowledgment targets; selecting US reads must not shrink an all-five-target write obligation.

## Available execution

1. Resolve effective policy, authorize access, capture/validate the read group and deadline, and enforce concurrency/resource limits.
2. Dispatch a candidate lookup to every distinct cluster in the group concurrently, including local. Apply normal candidate validation at each result.
3. On the first valid non-null value received before the deadline, return it without waiting for the other members, a newer value, or a quorum. Cancel unfinished work where supported; otherwise discard late results and release resources. Never wait for loser cleanup before returning the winner.
4. A valid null/expired candidate marks that member as empty. Return null immediately only if all members have replied with null and no requests remain pending.
5. A transient endpoint failure is not a value and must not cancel healthy attempts. Record it and continue the race. If no value is obtained and failures/pending attempts prevent an all-null completion, return null at the shared deadline. Invalid candidates never win; record their rejection and continue other attempts. Request-level authorization/configuration errors remain errors, not null.
6. At the deadline, return null if no winner was accepted. Discard values arriving afterward. Preserve caller cancellation and distinguish timeout-null from all-null in sanitized telemetry/result metadata, while the value remains null in both cases.

A first stale value wins even if a newer value is returned later. Neither a hit nor null proves current cross-device revocation status; that needs a separate authorization contract. Available performs no read repair, write-back, historical lookup, or lineage wait.

## Local execution

Read and validate one candidate at the local endpoint. Return its value or null on ordinary absence/expiry. Connectivity, authentication, and integrity failures remain explicit errors. Use bounded local request deadlines; Local does not inherit Available's timeout-to-null rule. It performs no remote read fallback or regional freshness wait.

## Proposed adapter API and configuration

These are behavioral proposals, not a shipping SDK schema.

| Operation | Behavior |
| --- | --- |
| `put(sessionId, payload, operationId)` | Store one immutable identified update at the origin and distribute under the configured write policy. |
| `get(sessionId)` | Available using the configured local read group and deadline. |
| `get(sessionId, { policy: "available", group: "US" })` | Race all configured US members, including local, after validating group membership. |
| `get(sessionId, { policy: "local" })` | Query only local. |

Configuration separates `distribution` (`active-active` or `independent`), `acknowledgment` (`local` baseline or explicit independent `all-targets`), independent `recovery` (`request-only` or `durable-replay`), `readPolicy` (`available` default or `local`), local endpoint, groups/read-group selection, target set/configuration epoch, deadlines, and fan-out limits. Reject unsupported policies (`session`, `greedy`, `required`, `latest`, `any`, and unimplemented `causal`/`coordinated`/`linearizable`). There is no public exact-version or caller-context read input.

## Data, writes, and recovery

Use Redis Software 8.x with three primary data shards per regional database and additional replica shards. Pin exact builds, commands, client, persistence, expiry, capacity, and conflict behavior. Suggested immutable envelope key: `session:{opaque-session-id}:snapshot:<generation>:<record-id>`; a local candidate hint may use `session:{opaque-session-id}:available`. The hint key name is storage plumbing, not the read fan-out policy.

The envelope binds session identity, schema, generation, record ID, payload, digest, and server-controlled absolute expiry. Record identity is for copying/retry verification; numeric labels such as 42/43 are not a global revision clock. Candidate publication follows successful snapshot storage and may lag or regress under the accepted backend conflict semantics; reads make no latest-state claim. Validate the exact candidate-selection/conflict rule before implementation. Read candidates by key, not scans.

Serialize a logical update as required by its business rules, allocate operation/record IDs once, and reuse them on retries. Copy the same envelope to destinations without repeating business mutations or resetting expiry. On ambiguous write acknowledgment, reconcile the same IDs at the origin; do not claim rollback or exactly-once execution. Conflicting identity/content is an integrity error.

Active-Active owns CRDT transport and strong eventual convergence. Independent mode must supply fan-out; request-only sends the next same-session update's current version and may leave an idle region stale indefinitely. Optional durable replay must atomically bind accepted snapshots to recoverable delivery obligations before success. Local acknowledgment does not wait for remote regions; all-target acknowledgment captures every configured target and reports partial/uncertain outcomes rather than shrinking the set. Readback verifies placement, not disk durability, atomic visibility, or linearizability. See [backends.md](backends.md).

## Causal ordering on Active-Active

**Causal** (`causal`) names a deployment-backed ordering behavior: read the selected regional instance of an Active-Active database with causal consistency enabled. Redis preserves causal relationships between operations on the same key across its participating instances. If the instance initiating B observed A on that key before B, other instances must observe A's effect before B's. A lagging instance may still expose neither update. This does not supply cross-key ordering, latest-completed-write discovery, or a catch-up guarantee for a caller moving regions.

This is native replication behavior, not a built-in per-request Redis read-concern setting. The proposed adapter option must validate the backend/database causal flag before admitting traffic; it cannot enable ordering by attaching a request label. Causal configuration covers the participating Active-Active database, independently of the groups used by Available reads. It does not perform an Available race or a Linearizable commit barrier.

Native causal ordering removes the custom replication-order enforcement that comparable ordering on independent clusters would require. Deployment validation, candidate/access checks, and adapter integration still need code. Reads remain regional and writes can use local acknowledgment; causal replication adds network traffic and memory/performance overhead. No numerical latency comparison with Coordinated or Linearizable has been established. See [Redis causal consistency](https://redis.io/docs/latest/operate/rs/databases/active-active/causal-consistency/).

## Linearizability and scope

The **Linearizable** option requires `distribution=active-active` as a project architecture constraint. Its contract is one history per key respecting real-time operation order for all callers in the selected geographic/global scope. Active-Active provides eventual convergence alone; ordering authority, commit rules, safe reads, fencing, partitions, and recovery require an additional validated protocol. This mode remains deferred and unsupported. The backend requirement is a project rule, not a claim that independent clusters can never implement linearizability.

## Proposed Coordinated option for independent clusters

**Coordinated** (`coordinated`) is the recommended label for the requested linearizable-like option on `distribution=independent`. It is a separate proposed option, not a renamed Available race, an Active-Active feature, or a current guarantee of linearizability. “Weak linearizable” does not specify which freshness or ordering properties hold, so the project does not use that label.

A candidate design would coordinate writes/reads through an application-managed authority and verify committed state before returning it. No authority mechanism, commit/read protocol, freshness bound, concurrent-write order, fencing/failover rule, or partition/deadline behavior has been selected. These must be specified and validated before claiming a guarantee or exposing the policy. A lock, majority of copies, or all-target placement alone is not such a protocol.

Proposed backend compatibility is `causal` with causal-enabled Active-Active, `coordinated` with independent clusters, and `linearizable` with Active-Active plus its additional protocol. Until each adapter/protocol integration is implemented and validated, reject it and all mismatched combinations rather than mapping it to Local/Available. None changes the Available default, reinstates Session, or changes existing write acknowledgment sets. Future protocols must define any new commit participants explicitly.

## Outcomes and observability

Local absence is null; Available all-null and deadline-without-value are also null. Preserve distinct telemetry for Local miss, Available all-null, Available deadline-null, winning region, rejected/failed attempts, cancellation, and per-region latency. Successful read metadata may include actual record identity, region, effective policy, and captured group, without exposing credentials or payloads in logs.

An internal write-placement verifier may report an expected snapshot as **snapshot missing**; that is separate from public read null semantics. Expiry is based on validated server-controlled expiry and an agreed clock-skew policy. Healthy endpoints, stored records, or a racing read do not establish current authorization after another device logs out.

## Requirements

| ID | Requirement | Proof |
| --- | --- | --- |
| R01 | Verify platform, backend, regional sizing, and client/command support | V01 |
| R02 | Bind immutable identity/content/expiry; preserve IDs on retry and copying | V02, V12 |
| R03 | Default to Available, with explicit Local and no Session/exact-version API | V03, V04, V11 |
| R04 | Available concurrently queries every captured group member including local | V05, V06, V10 |
| R05 | Return first valid non-null value without waiting for slower replies | V05, V07 |
| R06 | Continue after null replies; null only on all-null or deadline without value | V06, V08, V09 |
| R07 | Bound deadlines, fan-out, cancellation, and late-result cleanup | V08, V09, V13 |
| R08 | Apply authorization, identity, integrity, generation, and expiry checks | V02, V14 |
| R09 | Keep Local errors distinct; preserve Available outcome/error telemetry | V09, V14 |
| R10 | Separate read-group membership from write acknowledgment targets | V10, V15 |
| R11 | Preserve independent request-only and optional durable-replay contracts | V16, V17 |
| R12 | Preserve local/all-target acknowledgment and uncertain outcomes | V12, V15 |
| R13 | Validate restore/admission, expiry, retention, and configuration epochs | V18 |
| R14 | State stale-read and linearizability/revocation limits explicitly | V07, V19 |
| R15 | Measure end-to-end latency/outcome rates without leaking secrets | V13, V20 |
| R16 | Record project backend constraints: Coordinated targets independent clusters; Linearizable requires Active-Active plus coordination. Both remain unsupported without validated protocols. | V21 |
| R17 | Causal requires verified Active-Active causal configuration; promise per-key causal order without regional catch-up or cross-key freshness guarantees. | V22 |

## Open implementation decisions

Language/client, allowed group overrides, candidate/conflict rules, connection pooling, finite budgets, resource limits, exact capture/worker commands, persistence/retention, expiry/skew, and service levels remain unselected. Causal adapter integration requires validated deployment checks for the native causal flag. The Coordinated option additionally needs a precise freshness/ordering contract and authority/commit/read/failure protocol; the Linearizable Active-Active overlay is also unvalidated. Prototype results do not complete the production acceptance suite. See [sources.md](sources.md), [plan.md](plan.md), and [latency.md](latency.md).
