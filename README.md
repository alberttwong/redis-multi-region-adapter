# Redis Multi-Region Adapter

1. **Local:** Does my local cluster have a value?
2. **Available (default):** Does any cluster in my group have a value?
3. **Optional monotonic guarantee:** Can I read without going backward from what I have already seen?
4. **Linearizable over Active-Active:** Does this read reflect writes completed before it began, using Active-Active plus coordination?
5. **Linearizable over Coordinated:** Does this read reflect writes completed before it began, using independent clusters plus coordination?

**Available reads by default, with monotonic off.** Redis Multi-Region Adapter is a proposed adapter for Redis Software 8.x across regional databases. It separates where reads look, how writes reach other regions, and which guarantees require coordination.

**Status — 2026-11-09:** production design plus a legacy AWS/Terraform spike. The revised Local/Available API has no production SDK yet. Automatic monotonic enforcement and both linearizable protocols are unimplemented. The spike uses historical controls and does not implement the new Available group race. [spec.md](spec.md) is the authoritative behavior contract.

## Choose the behavior

These settings answer different questions; selecting a read policy does not select a write policy or replication backend.

| Decision | Options | Default / constraint |
| --- | --- | --- |
| **Read strategy** | `available` or `local` | **Available**. Linearizable variants below require future custom protocols. |
| **Read-history guarantee** | **Off** (`monotonic: false`) or **On** (`monotonic: true`, proposed), on Local/Available | **Off** (`monotonic: false`). On requires automatic caller history and trustworthy state-order validation. |
| **Read scope** | Configured geographic group or explicit global group | Available uses the local region's configured group, including local; allowed request overrides are explicit. Local contacts only local. |
| **Write distribution** | Redis Active-Active or adapter fan-out to independent clusters | Backend must be selected; neither deployment is assumed. |
| **Write acknowledgment** | `local`, or `all-targets` for independent clusters | **Local**. All-targets verifies every captured write target; read groups do not shrink that set. |
| **Native causal consistency** | On or off for Active-Active | Backend configuration, not a read policy; the project does not select a flag default. |
| **Delivery recovery** | No background repair for independent clusters; Redis-managed for Active-Active | Derived from the backend. No separate recovery selector or application replay worker. |

A linearizable option is a read **and write** protocol commitment. It cannot be supplied by changing a read label while keeping unconstrained writes. See [decisions.md](decisions.md) for configuration examples and deployment tradeoffs.

## Topology and groups

The example has six application clients and five regional databases. A1/A2 share one database; clients and shards are not extra regional targets.

| Read group | Clients and regional databases |
| --- | --- |
| **US** | A1/A2 → `us-west-2`; B1 → `us-east-1`; C1 → `us-east-2` |
| **EU** | D1 → `eu-west-1`; E1 → `eu-central-1` |
| **Global (optional)** | An explicitly configured group containing all five regional databases |

An Available group must contain the local cluster and resolve to distinct known endpoints. Selecting a US read group can coexist with writes targeting all five databases. Geographic/global describes scope, not a freshness guarantee. Local ignores group fan-out and has no automatic remote fallback.

The design targets three primary shards per regional database, with replicas additional: fifteen primaries across this example. This per-region sizing interpretation remains an assumption to confirm. See [consistency.md](consistency.md).

## Read behavior

### How Local and Available return a result

With monotonic off, **Local** validates one local candidate and returns its value or ordinary null. Connectivity, authentication, integrity, and local deadline failures remain errors.

**Available** starts requests to every read-group member concurrently, including local. It returns the first valid non-null value immediately, without comparing versions or waiting for agreement. It does not try local first and then fall back.

| Available outcome | Result |
| --- | --- |
| A valid non-null value arrives before the shared deadline | Return it; cancel or discard losing work without delaying the response. |
| One cluster replies null while others are pending | Keep waiting for a value within the shared deadline. |
| Every cluster replies null | Return null immediately. |
| No valid value arrives before the shared deadline | Return null, even if a value exists in a slow or unreachable cluster. |
| One endpoint fails or returns an invalid candidate | Record the failure/rejection and continue healthy attempts; without a winner, wait to the deadline unless all replies are null. |
| Request-level authorization or configuration is invalid | Return an error. |

Available chooses by arrival time. An older value can win; neither a hit nor timeout-null proves the latest state. All-null and deadline-null share a null value but need distinct telemetry. Available provides no read repair or write-back.

### Read behavior — Monotonic off (default)

`monotonic: false` does not enforce caller read history. The conditional causal ordering below comes from the Active-Active backend.

| Behavior | Main question | Backend | Ordering guarantee | Freshness guarantee | Read latency | Implementation status |
| --- | --- | --- | --- | --- | --- | --- |
| **Local** / `local` | Does my local cluster have a value? | Independent or Active-Active, regardless of native causal configuration | **No** causal-order guarantee for independent clusters or Active-Active with causal consistency disabled. **Yes—same-key causal operation order** with Active-Active causal consistency enabled. No caller read-history ordering guarantee. | **None.** May return stale data or ordinary null. | **fast** | **S — Proposed.** One regional lookup using shared client/validation code. |
| **Available** / `available` | Does any cluster in my group have a value? | Independent or Active-Active, regardless of native causal configuration | **No** causal-order guarantee for independent clusters or Active-Active with causal consistency disabled. **Yes—same-key causal operation order** with Active-Active causal consistency enabled. No caller read-history ordering guarantee. | **None.** May return stale data or ordinary null. | **slow** | **M — Proposed default.** Concurrent group fan-out, shared deadlines, validation, and loser cleanup. |
| **Linearizable over Active-Active** / `linearizable` | Does this read reflect writes completed before it began? | Active-Active + custom coordination | **Yes.** One real-time order per key within scope. | **Real-time freshness:** reflect writes completed before the read begins, within scope. Not implemented. | **slow++** | **XL — Deferred, unimplemented.** Custom ordering/commit/read protocol, fencing/failover, and fault validation; Active-Active supplies replication only. |
| **Linearizable over Coordinated** / `linearizable-coordinated` | Does this read reflect writes completed before it began? | Independent clusters + custom coordination | **Yes.** One real-time order per key within scope. | **Real-time freshness:** reflect writes completed before the read begins, within scope. Not implemented. | **slow++** | **XL — Proposed, unimplemented.** Custom ordering/commit/read and independent-cluster recovery/failover protocol with fault validation. |

### Read behavior — Monotonic on (proposed)

`monotonic: true` automatically carries each caller's last tracked successful read as a floor. Local rechecks only local state; Available filters the group race. Once an unexpired floor exists, no eligible state means bounded waiting followed by failure, rather than an older value or timeout-null. With no prior tracked observation, discovery follows the base strategy.

| Behavior | Main question | Backend | Ordering guarantee | Freshness guarantee | Read latency | Implementation status |
| --- | --- | --- | --- | --- | --- | --- |
| **Local** / `local` | Does my local cluster have a value? | Independent or Active-Active, regardless of native causal configuration | **Yes—per-caller non-regression** on the same key; Active-Active also preserves causal operation order when enabled. No global total order. | **Last-observed freshness:** at least the caller's last tracked successful observation, once established; not necessarily latest completed writes. | **slow+** | **L — Proposed, unimplemented.** Automatic read-history enforcement on local state only; wait locally or fail if the floor cannot be met. |
| **Available** / `available` | Does any cluster in my group have a value? | Independent or Active-Active, regardless of native causal configuration | **Yes—per-caller non-regression** on the same key; Active-Active also preserves causal operation order when enabled. No global total order. | **Last-observed freshness:** at least the caller's last tracked successful observation, once established; not necessarily latest completed writes. | **slow+** | **L — Proposed, unimplemented.** Automatic read-history enforcement filters the group race; wait/fail if no eligible state arrives. |
| **Linearizable over Active-Active** / `linearizable` | Does this read reflect writes completed before it began? | Active-Active + custom coordination | **Yes.** One real-time order per key within scope. | **Real-time freshness:** reflect writes completed before the read begins, within scope. Not implemented. | **slow++** | **XL — Deferred, unimplemented.** Custom ordering/commit/read protocol, fencing/failover, and fault validation; Active-Active supplies replication only. |
| **Linearizable over Coordinated** / `linearizable-coordinated` | Does this read reflect writes completed before it began? | Independent clusters + custom coordination | **Yes.** One real-time order per key within scope. | **Real-time freshness:** reflect writes completed before the read begins, within scope. Not implemented. | **slow++** | **XL — Proposed, unimplemented.** Custom ordering/commit/read and independent-cluster recovery/failover protocol with fault validation. |

The tables use the same strategies and columns. Both linearizable rows remain identical across tables because their real-time guarantee already includes monotonicity for sequential same-key operations within scope.

### What the guarantees mean

- **Backend causal order:** with native Active-Active causal consistency enabled, instances preserve causally related operations on the same Redis key. This applies to Local and Available, but does not make a lagging region current or prevent a caller from regressing across regions. Same-key ordering does not establish a cross-key snapshot/hint guarantee. See [Redis causal consistency](https://redis.io/docs/latest/operate/rs/databases/active-active/causal-consistency/).
- **Last-observed freshness:** monotonic enforcement prevents returning state older than the caller's tracked read floor. After reading 42, a later tracked read must return 42 or a proven later state, or fail. It may still miss newest 43; there is no maximum staleness-age guarantee. Raw numeric labels or unrelated record IDs do not prove history order.
- **Real-time freshness:** a linearizable read reflects writes completed before it began, or later state, within the coordinated scope. Concurrent operations must fit one real-time per-key order. If that cannot be established, wait/fail rather than serve stale data or deadline-null.

Monotonic tracks successful reads, not unread acknowledged writes: it does not supply read-your-own-writes. Turning it off retains but does not enforce or advance an existing floor; turning it back on resumes that floor. Automatic storage/transport, safe concurrent responses, and deletion/expiry/generation rules still need design and implementation.

Session and Causal are not separate public read options. There is no public exact-version selector. Local/Available and their proposed monotonic modifier work on either backend, with the Active-Active causal flag on or off. Reject removed or unimplemented options rather than silently weakening the requested guarantee.

### Reading the latency and effort columns

**Latency:** `fast` = regional path; `slow` = remote-response path; `slow+` = history verification/coordination or freshness waiting; `slow++` = extra sequential WAN phases or a deadline wait. These are planning bands, not measured bounds. Available can be fast when local wins and slow++ at timeout. Monotonic can return quickly when the floor is already met. Both linearizable implementations use **slow++ for reads and writes**; no measured speed ranking is established. See [latency.md](latency.md).

**Effort:** S = bounded feature; M = moderate concurrency/resource handling; L = substantial automatic history and correctness work; XL = distributed protocol and failure/recovery validation. Estimates assume shared clients, authorization, validation, and topology plumbing; they exclude infrastructure and a complete production SDK. The L history feature is shared by Local/Available, and linearizable read/write work is shared too, so sizes are not additive. Stronger-guarantee estimates have low confidence until the designs are selected.

## Write behavior

First choose distribution: **Active-Active** accepts one origin write and Redis handles replication; **independent clusters** require the adapter to copy the same immutable identified update to each configured target. Reuse IDs, content, and original absolute expiry on retries; copying must not repeat business mutations. Publish a discovery candidate only after storing its snapshot.

Then choose acknowledgment:

| Write behavior | Backend | Success acknowledged when | Ordering / visibility guarantee | Write latency | Status |
| --- | --- | --- | --- | --- | --- |
| **Local acknowledgment** / `local` | Independent, or Active-Active (causal consistency on or off) | The origin accepts the update under the selected durability policy. | Remote regions may lag. The acknowledgment alone adds no global ordering; native causal order applies only when Active-Active causal consistency is enabled. | **fast** | Baseline. No application replay capture or worker. |
| **All-target acknowledgment** / `all-targets` | Independent clusters | Every target in the captured write set verifies the same identified update. | Placement at acknowledgment; not atomic visibility, disk durability, or linearizability. | **slow+** | Proposed independent option; one missing target prevents success. |
| **Linearizable commit protocol** | Active-Active + custom coordination, or independent clusters + custom coordination | A future protocol establishes a safely ordered commit according to its authority/failure model. Exact commit rule remains unselected. | Target: the same real-time per-key guarantee for both linearizable implementations. Matching reads must use that protocol too. | **slow++** | Proposed/deferred; neither replication nor all-target placement alone provides it. |

Local acknowledgment is the baseline under either backend; an adapter all-target acknowledgment overlay for Active-Active is not specified. All-targets is available as a proposed independent-cluster option. The custom commit row is a future protocol responsibility, not an additional implemented `acknowledgment` value.

A write deadline does not mean null, rollback, or success. Report partial/uncertain outcomes, retain original IDs and the captured target set for reconciliation, and never silently remove an unreachable target. A later successful write does not retroactively acknowledge an earlier uncertain one. All-target placement alone provides neither linearizability nor atomic visibility or disk durability. The monotonic read modifier adds no write acknowledgment mode. See [backends.md](backends.md).

## Recovery

Here, recovery means completing missed inter-region delivery. Local Redis HA, restart/restore, and persistence remain separate operational concerns.

| Recovery | Backend | After incomplete delivery | Requires another write? |
| --- | --- | --- | --- |
| **No background repair** | Independent clusters | Bounded request-time fan-out; no persisted unfinished delivery obligations. Each later same-session write distributes its current value as normal write behavior. Without another write, a missed delivery can remain unrepaired indefinitely. | **Yes**, for another delivery attempt after the request ends. |
| **Redis-managed** | Active-Active | Redis handles replication and catch-up under its configured persistence/recovery behavior. No application replay worker is added. | **No**, for Redis-managed replication recovery. |

Each later independent same-session write distributes its current version as normal write fan-out. This is not a next-write recovery setting and need not restore missed historical versions. Writes to other sessions do not repair this session. There is no application outbox, durable replay option, or background repair worker in production scope.

Active-Active supplies eventual CRDT convergence through its native transport. Independent fan-out has no unconditional eventual-convergence guarantee after missed delivery: without another write, regions may differ indefinitely. “Eventual” describes convergence when delivery completes; it does not make independent clusters replicate automatically.

Backend delivery recovery does not create linearizability. Both future linearizable protocols must separately define authority, safe commit/read rules, fencing, failover, and recovery. The independent no-background-repair baseline does not remove those future protocol obligations.

## What remains open

The baseline design selects Available/Local, bounded fan-out, and local acknowledgment; it does not implement them as a production adapter. Decisions still needed include the SDK/client, exact Redis builds and supported commands, candidate/conflict rules, persistence and durability, expiry/skew, resource limits, allowed group overrides, and service levels.

Automatic monotonic history and both linearizable protocols need implementation and fault validation. Immediate cross-device revocation, cross-session transactions, historical backfill, and application background repair are outside the selected baseline. A read result alone does not establish current authorization. See [plan.md](plan.md), [validation.md](validation.md), and [sources.md](sources.md).

## AWS latency spike

The [legacy spike](spike/README.md) contains Terraform deployment, regional runners, historical preset A–E measurements, and reproduction/teardown instructions. Its recorded installer is pinned to Redis Software 8.2.6-25; this is an experimental configuration, not a claim about the latest release.

Its prototype read/write/replay paths and tests do not implement this revised production API or prove strict consistency. Replay presets C/E and historical control names remain intact as experimental evidence; they do not add replay to the production plan. Existing measurements do not predict the new Available group race.

## Documentation guide

| Document | Purpose |
| --- | --- |
| [intent.md](intent.md) | Goals, scope, and selected outcomes |
| [spec.md](spec.md) | Authoritative behavior contract and requirements |
| [consistency.md](consistency.md) | Guarantee definitions, topology, and examples |
| [decisions.md](decisions.md) | Configuration examples, diagrams, and tradeoffs |
| [backends.md](backends.md) | Distribution, acknowledgment, and recovery details |
| [latency.md](latency.md) | Latency planning and measurement methods |
| [validation.md](validation.md) | Requirements mapped to proposed acceptance scenarios |
| [plan.md](plan.md) | Implementation order and completion evidence |
| [operations.md](operations.md) | Failure handling, rollout, and monitoring |
| [REVIEW.md](REVIEW.md) | Review priorities |
| [CLAUDE.md](CLAUDE.md) | Concise implementation-session context |
| [sources.md](sources.md) | Evidence, selected decisions, assumptions, and open questions |

Repository Markdown is the design source of truth. External sources supply product evidence; the artifact structure follows the [AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook).
