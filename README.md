# Redis Multi-Region Adapter

## Why build this?

**This adapter provides a common way to access sessions across Redis Active-Active or a group of independent Redis clusters.** It defines where reads look, how long they wait, how writes reach other regions, and when a write can report success.

**Both backends support the same adapter read behavior.** With independent clusters, the adapter distributes session updates using write fan-out. With [Redis Active-Active](https://redis.io/docs/latest/operate/rs/databases/active-active/), Redis handles replication and catch-up. Active-Active additionally provides native CRDT conflict resolution, automatic replication recovery, and optional same-key causal ordering. Independent clusters use the adapter's smaller set of distribution capabilities. The choice depends on the capabilities, costs, and operational responsibilities your application needs.

Consider a session created in the US just before the user's next request reaches Europe. Before that update reaches Europe, a local read may return null or an older session on either backend. The adapter lets the application read only locally or search a configured group for a valid value within a deadline. Available can find a session in another region, while still allowing an older response to win.

Across five regions, the adapter supports Redis Active-Active or independent Redis clusters. Either approach may require less infrastructure than five separate deployments, each with one primary and four replicas. Actual savings depend on comparable capacity, throughput, high-availability requirements, network traffic, and operational costs. Active-Active includes additional native capabilities; independent clusters shift more responsibility to the application.

## What does it solve?

The proposed adapter gives applications one explicit session-access contract across either backend:

- **Regional session misses:** Local reads one regional database. Available concurrently queries every database in a configured geographic or global group, including local, so a local miss does not end the search while other regions may have the session.
- **Bounded read waiting:** Available returns the first valid non-null value within a shared deadline. It returns null if all members reply null or the deadline expires without a value; deadline-null does not prove absence everywhere.
- **Explicit write delivery and acknowledgment:** Active-Active owns replication and catch-up. Independent clusters use adapter write fan-out, with local acknowledgment by default or proposed all-target verification. All-target placement does not establish linearizability. Independent delivery has no background repair; missed updates can remain undelivered without another write to that session.
- **Clear consistency expectations:** Local and Available may return stale state and do not guarantee read-your-own-writes, caller monotonicity, or linearizability. The baseline read contract adds no monotonic or linearizable guarantee on either backend.

**Available reads by default, with monotonic off.** A proposed adapter for Redis Enterprise (Redis Software 8.x) across regional databases.

**Status:** design plus a [legacy AWS spike](spike/README.md), updated 2026-11-09. No production SDK implements this revised API yet. Automatic monotonic enforcement and both linearizable protocols are unimplemented. Use Redis Enterprise native features and existing client facilities; custom baseline work is limited to the selected adapter behavior. [spec.md](spec.md) defines the contract.

## Questions and answers

| # | Question | Answer |
| --- | --- | --- |
| 1 | **Read scope:** Local, geographic group, or global? | Local queries one cluster; Available races the selected group, including local. |
| 2 | **Read history:** Allow regression or preserve prior observations? | Monotonic **Off** permits regression; proposed **On** enforces the caller's same-key read floor. |
| 3 | **Freshness:** Any valid value or completed-write freshness? | Local/Available may be stale. Monotonic adds last-observed freshness; Linearizable targets completed-write freshness within scope. |
| 4 | **Coordination backend:** Active-Active or independent clusters? | Both have future Linearizable variants requiring custom coordination and matching writes. |
| 5 | **Read deadline:** How long to wait, then null or error? | Configured budget, with no default duration selected. Available normally returns null; Local timeout and unmet stronger guarantees cause errors. |
| 6 | **Distribution:** Who sends regional copies? | Redis for Active-Active; adapter fan-out for independent clusters. |
| 7 | **Acknowledgment:** Local acceptance or every target? | Local by default; independent clusters can use all-target verification. |
| 8 | **Linearizable commit:** Must reads and writes share a real-time order? | Only through a future matching read/write coordination protocol. |
| 9 | **Missed delivery:** Who retries? | Redis handles Active-Active catch-up. Independent clusters have no background repair; later same-session writes send current state. |

[Read behavior](#read-behavior) covers 1–5; [Distribution](#distribution) covers 6; [Write behavior](#write-behavior) covers 7–8; [Recovery](#recovery) covers 9.

## Choose the behavior

| Decision | Question | Options | Default / constraint |
| --- | --- | --- | --- |
| **Read strategy** | 1, 3–4 | `local`, `available`, future `linearizable` / `linearizable-coordinated` | **Available**. Linearizable variants require their named backend and matching write protocol. |
| **Read-history guarantee** | 2 | **Off** (`monotonic: false`); proposed **On** (`monotonic: true`) | **Off**. On applies to Local/Available; linearizability already implies sequential same-key non-regression. |
| **Read scope** | 1 | Local; geographic group; explicit global group | Available's configured group must include local. Future linearizable scope is protocol-defined. |
| **Read deadline** | 5 | Finite configured budget; proposed `readDeadlineMs` for Available | **No default duration selected.** One shared budget for the group race. |
| **Write distribution** | 6 | **Redis-managed** (Active-Active); **Adapter fan-out** (independent) | Both supported; backend must be configured explicitly. Active-Active supplies additional native capabilities. Read groups do not change write targets. |
| **Native causal consistency** | Supporting setting | **Off** or **On** for Active-Active | No project-selected flag default. Same-key causal order does not supply caller monotonicity or linearizability. |
| **Write acknowledgment** | 7 | `local`; `all-targets` (independent only) | **Local**. All-target placement is not linearizability. |
| **Commit guarantee** | 8, paired with 3–4 | Baseline acknowledgment; future **Linearizable commit protocol** | No baseline custom commit protocol; stronger mode requires coordinated reads and writes. |
| **Delivery recovery** | 9 | **No background repair** (independent); **Redis-managed** (Active-Active) | Derived from backend; no separate recovery selector. |

Reject unimplemented guarantees rather than silently weakening them. See [configuration examples](decisions.md#example-code-configuration-writes-and-reads).

## Read behavior

**Local** returns one validated local value or null; infrastructure/integrity failures remain errors. **Available** concurrently queries every group member and returns the first valid non-null value. Early nulls or endpoint failures do not stop healthy attempts. Return null when all members reply null or the shared deadline expires without a winner; timeout-null does not prove absence. Request-level authorization/configuration failures remain errors.

With an established unexpired monotonic floor, no eligible candidate means wait/fail rather than an older value or timeout-null. Local stays local-only; Available filters its group race. See [execution and deadline rules](spec.md#available-execution) and the proposed [`readDeadlineMs` configuration](decisions.md#configure-six-clients-in-us-and-eu-groups-preset-b).

### Read behavior — Monotonic off (default)

| Behavior | Main question | Backend | Ordering guarantee | Freshness guarantee | Read latency | Implementation status |
| --- | --- | --- | --- | --- | --- | --- |
| **Local** / `local` | Does my local cluster have a value? | Independent or Active-Active, regardless of native causal configuration | **No** causal-order guarantee for independent clusters or Active-Active with causal consistency disabled. **Yes—same-key causal operation order** with Active-Active causal consistency enabled. No caller read-history ordering guarantee. | **None.** May return stale data or ordinary null. | **fast** | **S — Proposed.** One regional lookup using shared client/validation code. |
| **Available** / `available` | Does any cluster in my group have a value? | Independent or Active-Active, regardless of native causal configuration | **No** causal-order guarantee for independent clusters or Active-Active with causal consistency disabled. **Yes—same-key causal operation order** with Active-Active causal consistency enabled. No caller read-history ordering guarantee. | **None.** May return stale data or ordinary null. | **slow** | **M — Proposed default.** Concurrent group fan-out, shared deadlines, validation, and loser cleanup. |
| **Linearizable over Active-Active** / `linearizable` | Does this read reflect writes completed before it began? | Active-Active + custom coordination | **Yes.** One real-time order per key within scope. | **Real-time freshness:** reflect writes completed before the read begins, within scope. Not implemented. | **slow++** | **XL — Deferred, unimplemented.** Custom ordering/commit/read protocol, fencing/failover, and fault validation; Active-Active supplies replication only. |
| **Linearizable over Coordinated** / `linearizable-coordinated` | Does this read reflect writes completed before it began? | Independent clusters + custom coordination | **Yes.** One real-time order per key within scope. | **Real-time freshness:** reflect writes completed before the read begins, within scope. Not implemented. | **slow++** | **XL — Proposed, unimplemented.** Custom ordering/commit/read and independent-cluster recovery/failover protocol with fault validation. |

### Read behavior — Monotonic on (proposed)

| Behavior | Main question | Backend | Ordering guarantee | Freshness guarantee | Read latency | Implementation status |
| --- | --- | --- | --- | --- | --- | --- |
| **Local** / `local` | Does my local cluster have a value? | Independent or Active-Active, regardless of native causal configuration | **Yes—per-caller non-regression** on the same key; Active-Active also preserves causal operation order when enabled. No global total order. | **Last-observed freshness:** at least the caller's last tracked successful observation, once established; not necessarily latest completed writes. | **slow+** | **L — Proposed, unimplemented.** Automatic read-history enforcement on local state only; wait locally or fail if the floor cannot be met. |
| **Available** / `available` | Does any cluster in my group have a value? | Independent or Active-Active, regardless of native causal configuration | **Yes—per-caller non-regression** on the same key; Active-Active also preserves causal operation order when enabled. No global total order. | **Last-observed freshness:** at least the caller's last tracked successful observation, once established; not necessarily latest completed writes. | **slow+** | **L — Proposed, unimplemented.** Automatic read-history enforcement filters the group race; wait/fail if no eligible state arrives. |
| **Linearizable over Active-Active** / `linearizable` | Does this read reflect writes completed before it began? | Active-Active + custom coordination | **Yes.** One real-time order per key within scope. | **Real-time freshness:** reflect writes completed before the read begins, within scope. Not implemented. | **slow++** | **XL — Deferred, unimplemented.** Custom ordering/commit/read protocol, fencing/failover, and fault validation; Active-Active supplies replication only. |
| **Linearizable over Coordinated** / `linearizable-coordinated` | Does this read reflect writes completed before it began? | Independent clusters + custom coordination | **Yes.** One real-time order per key within scope. | **Real-time freshness:** reflect writes completed before the read begins, within scope. Not implemented. | **slow++** | **XL — Proposed, unimplemented.** Custom ordering/commit/read and independent-cluster recovery/failover protocol with fault validation. |

Native causal order preserves same-key operation dependencies within Active-Active instances; it does not make lagging regions current or prevent cross-region caller regression. Monotonic provides a last-observed floor, not latest-write freshness, a staleness-age bound, or read-your-own-writes. With no prior tracked read, discovery follows the base strategy. Linearizable rows are identical in both tables because that stronger guarantee already includes sequential same-key monotonicity. See [guarantee definitions](spec.md#freshness-terminology).

**Planning labels:** read/write latency uses `fast`, `slow`, `slow+`, `slow++`; both Linearizable variants are **slow++** for reads and writes. These are unmeasured bands, not bounds. Effort sizes S/M/L/XL are rough, shared work is not additive, and stronger-guarantee estimates have low confidence. Definitions: [latency.md](latency.md#qualitative-latency-labels), [plan.md](plan.md#effort-estimates).

## Distribution

Who sends the write is separate from when it may return success.

| Distribution | Backend | How a write reaches other regions | Who handles missed delivery? |
| --- | --- | --- | --- |
| **Redis-managed** | Active-Active | Application writes once to its local database; Redis replicates to participating regions. | Redis, through native replication and catch-up. |
| **Adapter fan-out** | Independent clusters | Adapter sends the same immutable identified update to every configured write target. | No background repair. A later same-session write distributes its current value; without another write, missed delivery can remain unrepaired indefinitely. |

The example uses five regional databases: US has `us-west-2` (A1/A2), `us-east-1` (B1), and `us-east-2` (C1); EU has `eu-west-1` (D1) and `eu-central-1` (E1). Global explicitly includes all five. Six clients are not six targets. Three primary shards per database, plus replicas, remains the sizing assumption. See [topology and groups](spec.md#group-membership-and-deadlines).

## Write behavior

| Write behavior | Backend | Success acknowledged when | Ordering / visibility guarantee | Write latency | Status |
| --- | --- | --- | --- | --- | --- |
| **Local acknowledgment** / `local` | Independent, or Active-Active (causal consistency on or off) | The origin accepts the update under the selected durability policy. | Remote regions may lag. The acknowledgment alone adds no global ordering; native causal order applies only when Active-Active causal consistency is enabled. | **fast** | Baseline. No application replay capture or worker. |
| **All-target acknowledgment** / `all-targets` | Independent clusters | Every target in the captured write set verifies the same identified update. | Placement at acknowledgment; not atomic visibility, disk durability, or linearizability. | **slow+** | Proposed independent option; one missing target prevents success. |
| **Linearizable commit protocol** | Active-Active + custom coordination, or independent clusters + custom coordination | A future protocol establishes a safely ordered commit according to its authority/failure model. Exact commit rule remains unselected. | Target: the same real-time per-key guarantee for both linearizable implementations. Matching reads must use that protocol too. | **slow++** | Proposed/deferred; neither replication nor all-target placement alone provides it. |

A timed-out write is not rollback or success: preserve original IDs and report partial/uncertain outcomes. All-targets is independent-only in this proposal. Linearizable commit is a future protocol responsibility, not an implemented acknowledgment selector. See [write/distribution details](backends.md#fan-out-and-acknowledgment).

## Recovery

This table concerns missed regional delivery; local Redis HA, restore, and persistence remain separate concerns.

| Recovery | Backend | After incomplete delivery | Requires another write? |
| --- | --- | --- | --- |
| **No background repair** | Independent clusters | Bounded request-time fan-out; no persisted unfinished delivery obligations. Each later same-session write distributes its current value as normal write behavior. Without another write, a missed delivery can remain unrepaired indefinitely. | **Yes**, for another delivery attempt after the request ends. |
| **Redis-managed** | Active-Active | Redis handles replication and catch-up under its configured persistence/recovery behavior. No application replay worker is added. | **No**, for Redis-managed replication recovery. |

Later same-session fan-out is normal write behavior, not a recovery setting or historical-backfill promise. Without another write, independent copies may differ indefinitely. No application outbox or replay worker is planned. Future linearizable protocols must separately define safe commit recovery and failover. See [backends.md](backends.md#no-background-repair-for-independent-clusters).

## Further reading

- [spec.md](spec.md): authoritative contract, execution rules, and guarantees.
- [intent.md](intent.md), [consistency.md](consistency.md), [decisions.md](decisions.md): scope, topology, configuration examples, and tradeoffs.
- [backends.md](backends.md), [operations.md](operations.md): distribution, acknowledgment, recovery, and operations.
- [plan.md](plan.md), [validation.md](validation.md), [REVIEW.md](REVIEW.md): implementation work, estimates, and acceptance criteria.
- [sources.md](sources.md), [CLAUDE.md](CLAUDE.md): provenance, open decisions, and implementation-session context.
- [AWS spike](spike/README.md): historical deployment and measurements. Its old read/replay controls do not implement or validate this revised API; experimental replay presets do not add replay to production scope.
