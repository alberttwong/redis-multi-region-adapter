# Specification: regional read behaviors

Date: 2026-11-09. Status: revised production design; implementation proposed.

Inputs: [intent.md](intent.md), [sources.md](sources.md). Proof: [validation.md](validation.md).

## Selected contract

The public default is **Available** (`available`): concurrently query every regional cluster in the selected read group, including the local cluster, and return the first valid non-null candidate. A null reply never wins over an outstanding request that may return a value. If every cluster returns null, return null immediately. If the shared deadline expires before a valid value is obtained, return null even when some clusters have not replied.

**Local** (`local`) reads only the selected local cluster and returns its valid candidate or null. Redis Active-Active owns propagation in that backend; independent regional databases require adapter-managed write distribution. Local reads do not start regional read fan-out.

With monotonic off, neither behavior guarantees read-your-own-writes, monotonic reads, or the newest completed write. Enabling the proposed modifier prevents read regression but still does not guarantee latest state or unread acknowledged writes. Different values may exist; Available returns whichever valid value arrives first without comparing versions or waiting for agreement. Null on deadline is an availability outcome, not proof of absence throughout the group.

The Session and Causal read options and custom causal protocol workstream have been removed. Monotonic is a proposed boolean modifier over successful Local/Available reads, default `false`, not a separate policy; it does not promise visibility of an unread acknowledged write. Record identities remain internal distribution/idempotency metadata, not a public read selector or freshness requirement. The experimental spike retains legacy controls and results; it is not this production API.

## Freshness terminology

For Local/Available, `monotonic: false` supplies no per-caller read-order guarantee; `monotonic: true` supplies per-caller non-regression on the same key in the accepted history, once a floor exists. This is not a cross-caller/global total order.

The docs distinguish **last-observed freshness** from **real-time freshness**. The monotonic modifier provides a last-observed floor: a successful read reflects at least the caller's last tracked successful observation, once that floor is established. This is read non-regression, not a maximum staleness age or discovery of the latest completed write. With monotonic off, Local/Available supply no freshness floor. The linearizable contracts require real-time freshness relative to writes completed before the read begins, within the selected scope. Unavailable required state causes waiting/failure, not a successful result that violates the chosen guarantee. Proposed/unimplemented status does not change these target definitions.

## Public read policies

| Behavior / policy | Scope | Result |
| --- | --- | --- |
| **Local** / `local` | Local cluster only, on either backend; Active-Active causal flag may be on or off | Valid local candidate or null; local infrastructure failures remain errors. |
| **Available** / `available` (default) | Every member of the selected group, including local, on either backend; Active-Active causal flag may be on or off | First valid non-null value; null if all replies are null or the deadline expires without a value. |
| **Linearizable over Active-Active** / `linearizable` (deferred) | Active-Active + custom ordering/commit/read protocol | Real-time order per key; reflect writes completed before a read begins. Additional protocol unimplemented. |
| **Linearizable over Coordinated** / `linearizable-coordinated` (proposed) | Independent clusters + custom ordering/commit/read protocol | The same linearizable guarantee; protocol unimplemented. |

Resolve policy and modifier from request overrides or store configuration, initially `policy=available` and `monotonic=false`. The base Local/Available algorithms below describe monotonic off; the modifier adds the checks specified in its own section. A Local or Available read still checks caller authorization, session/key binding, integrity, generation policy, and expiry. Policy selection never bypasses access checks.

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
| `get(sessionId, { policy: "local" })` | Query only local, with monotonic off unless enabled in the effective configuration. |
| `get(sessionId, { policy: "local", monotonic: true })` (proposed) | Query/recheck only local state while enforcing the caller's last tracked read floor. |
| `get(sessionId, { policy: "available", monotonic: true })` (proposed) | Race group members including local and accept only candidates satisfying the caller's last tracked read floor. |

Configuration separates `distribution` (`active-active` or `independent`), `acknowledgment` (`local` baseline or explicit independent `all-targets`), `readPolicy` (`available` default or `local`), proposed boolean `monotonic` (`false` default), local endpoint, groups/read-group selection, target set/configuration epoch, deadlines, and fan-out limits. Reject unsupported policies (`session`, `greedy`, `required`, `latest`, `any`, removed `causal`/`causal-coordinated`, ambiguous `coordinated`, obsolete standalone `monotonic`, and unimplemented `linearizable`/`linearizable-coordinated`). Reject `monotonic: true` until the modifier integration is implemented; never silently ignore it. Non-boolean modifier values are invalid. There is no public exact-version or caller-context read input.

## Delivery recovery by backend

- Independent clusters have **no background repair**. Bounded request-time fan-out does not persist unfinished delivery work. Each later same-session write distributes its current version as normal write behavior; idle regions may remain stale indefinitely.
- Active-Active has **Redis-managed** replication recovery, with no application capture or replay worker. Redis persistence and durability settings remain separate.
- Recovery is derived from distribution, not a public selector. Reject obsolete `recovery` configuration, including `request-only`, `next-write-refresh`, `durable-replay`, `not-applicable`, and `redis-managed` values, instead of silently accepting an unsupported setting. These labels do not select a Redis server parameter.

Read strategy, monotonic settings, groups, and acknowledgment do not change this backend behavior. Future linearizable protocols still need their own validated recovery rules. The legacy spike retains historical replay controls and measurements outside this production scope.

## Data, writes, and recovery

The [write behavior table](README.md#write-behavior) separates local acceptance, independent all-target placement, and future linearizable commit rules. Distribution and acknowledgment remain distinct; delivery recovery follows the backend. Future custom commit conditions are unselected; an Available read deadline returning null never implies an analogous successful write or rollback.

Use Redis Software 8.x with three primary data shards per regional database and additional replica shards. Pin exact builds, commands, client, persistence, expiry, capacity, and conflict behavior. Suggested immutable envelope key: `session:{opaque-session-id}:snapshot:<generation>:<record-id>`; a local candidate hint may use `session:{opaque-session-id}:available`. The hint key name is storage plumbing, not the read fan-out policy.

The envelope binds session identity, schema, generation, record ID, payload, digest, and server-controlled absolute expiry. Record identity is for copying/retry verification; numeric labels such as 42/43 are not a global revision clock. Candidate publication follows successful snapshot storage and may lag or regress under the accepted backend conflict semantics; reads make no latest-state claim. Validate the exact candidate-selection/conflict rule before implementation. Read candidates by key, not scans.

Serialize a logical update as required by its business rules, allocate operation/record IDs once, and reuse them on retries. Copy the same envelope to destinations without repeating business mutations or resetting expiry. On ambiguous write acknowledgment, reconcile the same IDs at the origin; do not claim rollback or exactly-once execution. Conflicting identity/content is an integrity error.

Active-Active owns CRDT transport and strong eventual convergence. Independent mode must supply fan-out; each same-session write sends its current version and may leave an idle region stale indefinitely after incomplete delivery. No unfinished delivery work is persisted for background repair. Local acknowledgment does not wait for remote regions; all-target acknowledgment captures every configured target and reports partial/uncertain outcomes rather than shrinking the set. Readback verifies placement, not disk durability, atomic visibility, or linearizability. See [backends.md](backends.md).

## Proposed monotonic modifier

`monotonic: true` asks: “Can I read without going backward from what I have already seen?” It adds the same guarantee to Local or Available on either backend; it is not a `policy` value. Default `monotonic: false` preserves the base read behavior. Automatically retain each caller's last successful tracked state per key, transport that protected floor across requests/regions, and accept the same or a proven later state. Only successful reads with monotonic enabled establish/advance the floor; unread writes and untracked off-reads do not. Off-reads may regress but must never reduce a retained floor. Re-enabling the modifier resumes that retained floor; an expected floor that was lost is an error, not a new first read.

| Effective strategy | Monotonic off | Monotonic on |
| --- | --- | --- |
| Local | One regional candidate; ordinary null/expiry or Local infrastructure errors. | Look up/recheck only the local candidate. If it meets the floor, return it; otherwise wait locally within the budget or fail. Never launch remote reads. |
| Available | Concurrent group race including local; first valid non-null, or null on all-null/deadline. | Race the same group, accepting the first value satisfying the floor. Continue after older/null/incomparable candidates; bounded rechecks can wait for eligible state. With an established unexpired floor, no eligible state by deadline is an error, not arbitrary null. |

With genuinely no prior floor, the first monotonic-on read follows its base strategy's discovery and ordinary absence/error behavior and establishes a floor when an observed state is returned. Once a floor exists, older/null/incomparable state cannot win. No acceptable state yields a typed history/freshness-unavailable error; the modifier overrides Available's all-null/deadline-null success when that would violate the floor. It never waits for the newest completed write.

Preserve the floor across region, group, and Local/Available strategy changes while the modifier remains enabled. A strategy change does not broaden Local into a group search or reset history. For sequential operations on the same key in the same linearizable scope, linearizability already implies monotonic reads; the flag is redundant and must never weaken the stronger contract.

A reliable version/history relation is required; arbitrary IDs, numeric labels, arrival time, or Redis last-write-wins alone do not prove that one state succeeds another. Define how concurrent versions, deletions, expiry, generations, and previously absent state participate in that history before implementation. A verified later deletion/tombstone may establish absence; a missing unexpired expected state cannot silently become null. Invalid/lost expected floors must not be treated as a first read. Middleware must serialize or otherwise safely combine a caller's concurrent read responses so the floor cannot roll back.

Both Local/Available strategies on either backend need this automatic read-history integration when enabled; Active-Active supplies replication but its optional causal flag does not track the last state seen by a caller moving regions. Independent clusters additionally need an accepted state-ordering/evidence mechanism. No mechanism, token/state lifecycle, failure contract, or production SDK is implemented. Business code selects the behavior without manually passing versions. Writes do not by themselves advance the read floor; the removed Session/RYOW policy is not reinstated. See the [monotonic-read definition](https://www.mongodb.com/docs/manual/core/read-isolation-consistency-recency/#causal-consistency).

## Linearizable implementations and scope

**Linearizable over Active-Active** (`linearizable`) uses Active-Active plus an application ordering/commit/read protocol. **Linearizable over Coordinated** (`linearizable-coordinated`) uses independent clusters plus such a protocol. The backend is the implementation distinction; both target **one real-time order per key** for every participating read and write in a captured geographic/global scope. A read beginning after a completed write must reflect that write or a later one, including committed deletion/absence. If freshness cannot be established, wait within a bound or fail explicitly; never substitute a stale value or Available-style deadline-null.

Both protocols must cover write authority/serialization, safe commit/read rules, durability assumptions, fencing, failover, concurrent operations, partitions, deadlines, and recovery. No protocol is selected or validated. Native Active-Active causal ordering, CRDT convergence, a lock alone, or all-target copy placement is insufficient to establish linearizability. The independent implementation can target the same full guarantee; it is not inherently “weak.” Both implementations carry **slow++** planning ratings for reads and writes. Actual latency depends on the protocol and topology; the band is not a measured SLO or universal lower bound, and no speed advantage for either backend is established.

## Backend validation and implementation status

Local/Available remain the current baseline with Available as default. The proposed monotonic modifier can be enabled on Local/Available on either backend only after its automatic caller-history/state-ordering integration is validated. Active-Active native causal consistency is optional backend configuration, not a read-policy selector or substitute for Monotonic enforcement.

`linearizable` uses Active-Active plus its custom protocol; `linearizable-coordinated` uses independent clusters plus its custom protocol. Reject unimplemented options, removed `causal`/`causal-coordinated`/Session/exact-version selectors, and mismatched configurations rather than downgrading. Each custom protocol must define its participants/conditions. None changes the existing write acknowledgment set automatically.

## Outcomes and observability

Local absence is null; Available all-null and deadline-without-value are also null. Preserve distinct telemetry for Local miss, Available all-null, Available deadline-null, winning region, rejected/failed attempts, cancellation, and per-region latency. Successful read metadata may include actual record identity, region, effective policy, effective monotonic flag, and captured group, without exposing credentials or payloads in logs.

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
| R11 | Independent request-time fan-out has no background repair; Active-Active recovery is Redis-managed; reject obsolete recovery configuration | V16, V17, V21 |
| R12 | Preserve local/all-target acknowledgment and uncertain outcomes | V12, V15 |
| R13 | Validate restore/admission, expiry, retention, and configuration epochs | V18 |
| R14 | State stale-read and linearizability/revocation limits explicitly | V07, V19 |
| R15 | Measure end-to-end latency/outcome rates without leaking secrets | V13, V20 |
| R16 | Validate guarantee/backend mapping and reject all unimplemented or mismatched stronger options; replace ambiguous Coordinated with its two explicit guarantees. | V21 |
| R17 | Proposed monotonic-on Local/Available provide last-observed freshness by automatically preserving per-caller successful-read history across regions on either backend; reject regression, lost floors, and unprovable state. | V22, V23 |
| R18 | Both linearizable implementations target the same real-time per-key freshness guarantee, including bounded wait/failure rather than stale/timeout-null results. | V24 |

## Open implementation decisions

Language/client, allowed group overrides, candidate/conflict rules, connection pooling, finite budgets, resource limits, persistence/retention, expiry/skew, and service levels remain unselected. The monotonic modifier needs automatic floor storage/transport, concurrent response sequencing, and proof of accepted state ordering including absence/expiry; both Linearizable implementations need ordering/commit/read/failover protocols. None is selected or validated. Prototype results do not complete the production acceptance suite. See [sources.md](sources.md), [plan.md](plan.md), and [latency.md](latency.md).

Local and Available inherit same-key causal operation ordering when Active-Active causal consistency is enabled. This backend ordering does not ensure a region has caught up or prevent a caller from reading older state after switching regions. With monotonic on, both strategies additionally enforce per-caller same-key non-regression using automatic read history; independent clusters need that enforcement too. Neither causal ordering nor monotonic reads guarantees the latest completed write. Same-key Redis ordering must not be assumed to order multiple snapshot/hint keys.
