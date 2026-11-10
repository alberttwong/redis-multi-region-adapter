# Redis Multi-Region Adapter

**Read questions**

1. **Read scope:** Should the read look only locally, across a geographic group, or across all regions?
2. **Read history:** May successive reads go backward, or must they preserve what the caller has already seen?
3. **Freshness:** May the read return any valid value, or must it reflect writes completed before it began?
4. **Coordination backend (proposed):** If linearizable reads are required, should the protocol use Active-Active or independent clusters?
5. **Read deadline:** How long may the read wait, and does reaching the deadline return null or an error under the chosen guarantee?

**Write questions**

6. **Distribution:** Does Redis replicate this write, or does the adapter send it to independent clusters?
7. **Acknowledgment:** Can the write succeed after local acceptance, or must every configured target verify it?
8. **Linearizable commit (proposed):** Is this write committed in one real-time order with all participating reads and writes within scope?
9. **Missed delivery:** Does Redis retry delivery, or can it remain incomplete until another write to the same session?

The [Read behavior section](#read-behavior) answers questions 1–5, with the tables comparing strategies and guarantees; [Distribution](#distribution) answers question 6; [Write behavior](#write-behavior) answers questions 7–8; [Recovery](#recovery) answers question 9. Linearizable reads and commits require matching future custom protocols.

**Available reads by default, with monotonic off.** Redis Multi-Region Adapter is a proposed adapter for Redis Software 8.x across regional databases. It separates where reads look, how writes reach other regions, and which guarantees require coordination.

**Status — 2026-11-09:** production design plus a legacy AWS/Terraform spike. The revised Local/Available API has no production SDK yet. Automatic monotonic enforcement and both linearizable protocols are unimplemented. The spike uses historical controls and does not implement the new Available group race. [spec.md](spec.md) is the authoritative behavior contract.

## Questions and answers

| # | Question | Answer | Details |
| --- | --- | --- | --- |
| 1 | **Read scope:** Local, geographic group, or global? | Local queries one cluster. Available races the configured geographic/global group, including local. Future linearizable scope must be defined by its protocol. | [Topology and groups](#topology-and-groups), [Read behavior](#read-behavior) |
| 2 | **Read history:** May successive reads go backward? | **Off:** regression is permitted. **On:** proposed automatic monotonic enforcement prevents the caller from reading older state on the same key. | [Monotonic off](#read-behavior--monotonic-off-default), [Monotonic on](#read-behavior--monotonic-on-proposed) |
| 3 | **Freshness:** Any valid value, or completed-write freshness? | Local/Available may return stale values. Monotonic adds a last-observed floor. Linearizable targets completed-write freshness within scope. | [Read behavior](#read-behavior), freshness columns |
| 4 | **Coordination backend:** Active-Active or independent clusters? | Both have proposed Linearizable variants requiring custom coordination and matching writes. | [Read behavior](#read-behavior), backend columns |
| 5 | **Read deadline:** How long to wait, then null or error? | Finite configured deadline; no default duration selected. Available with monotonic off returns null without a winner. Local deadline failures are errors. With an established unexpired monotonic floor, no eligible value means failure; future linearizable reads fail if freshness cannot be established. | [Read deadline chooser](#choose-the-behavior), [Read execution](#how-local-and-available-return-a-result) |
| 6 | **Distribution:** Who sends regional copies? | Redis for Active-Active; adapter fan-out for independent clusters. | [Distribution](#distribution) |
| 7 | **Acknowledgment:** Local acceptance or every target? | Local by default; independent clusters can use proposed all-target verification. | [Write behavior](#write-behavior) |
| 8 | **Linearizable commit:** Must writes share a real-time order with reads? | Only through a future matching read/write coordination protocol, on either named backend. | [Write behavior](#write-behavior) |
| 9 | **Missed delivery:** Who retries? | Redis handles Active-Active catch-up. Independent clusters have no background repair; later same-session writes distribute current state without promising historical repair. | [Recovery](#recovery) |

Deadline behavior is explained in the read execution text; the two read comparison tables keep their existing columns. Native causal consistency remains supporting backend configuration, not a separate headline question or an automatic monotonic/linearizable guarantee. Automatic monotonic enforcement and both linearizable protocols remain **proposed and unimplemented**.

## Choose the behavior

The chooser summarizes the detailed tables in the same order: reads, distribution, write acknowledgment/commit, and delivery recovery. Question numbers connect each choice to the list above. Read scope and deadlines have their own questions; the native causal flag remains supporting backend configuration.

| Decision | Question | Options | Default / constraint |
| --- | --- | --- | --- |
| **Read strategy** | 1, 3–4 | **Local** (`local`), **Available** (`available`), or future **Linearizable over Active-Active** (`linearizable`) / **Linearizable over Coordinated** (`linearizable-coordinated`) | **Available**. Local/Available are the proposed baseline; both Linearizable variants are unimplemented custom protocols with their named backends. |
| **Read-history guarantee** | 2 | **Off** (`monotonic: false`) or **On** (`monotonic: true`, proposed), on Local/Available | **Off** (`monotonic: false`). On needs automatic caller-history enforcement. Linearizable already implies non-regression for sequential same-key operations within scope. |
| **Read scope** | 1 | Local cluster; configured geographic group; explicit global group | Local contacts only local. Available uses the local region's configured group, including local, with validated allowed overrides. Future linearizable coordination scope must be defined by its protocol. |
| **Read deadline** | 5 | A finite deployment-configured budget; proposed `readDeadlineMs` for the Available group race | **No default duration selected.** One shared budget for the entire race. Local and stronger guarantees retain their documented timeout/error semantics. |
| **Write distribution** | 6 | **Redis-managed** replication for Active-Active; **Adapter fan-out** for independent clusters | Backend must be selected; neither deployment is assumed. Read groups do not change write targets. |
| **Native causal consistency** | Supporting setting | **Off** or **On** for Active-Active | Backend configuration, not a read policy; no project-selected flag default. Same-key causal ordering does not supply caller monotonicity or linearizability. |
| **Write acknowledgment** | 7 | **Local acknowledgment** (`local`) or **All-target acknowledgment** (`all-targets`, independent only) | **Local** for the baseline. All-targets verifies every captured write target and does not establish linearizability. |
| **Commit guarantee** | 8, paired with 3–4 | Baseline acknowledgment semantics, or a future **Linearizable commit protocol** over either named backend | Baseline adds no custom linearizable commit protocol. Linearizable requires matching coordinated reads and writes; it is not an extra implemented acknowledgment setting. |
| **Delivery recovery** | 9 | **No background repair** for independent clusters; **Redis-managed** for Active-Active | Derived from the backend. No separate recovery selector or application replay worker. Future linearizable protocols must additionally define commit recovery. |

A linearizable option is a read **and write** protocol commitment. Selecting it cannot retain unconstrained baseline writes. Monotonic-on and both Linearizable variants must be rejected until implemented; none is supplied simply by enabling native Active-Active causal consistency. See [decisions.md](decisions.md) for configuration examples and deployment tradeoffs.

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

The proposed **`readDeadlineMs`** setting bounds the entire Available race, rather than giving each member a separate sequential timeout. For example, `readDeadlineMs: 100` allows up to 100 ms for a winning value; this is illustrative, not a selected default or measured SLO. With monotonic off, no winner by the deadline returns null. With monotonic on and an established unexpired floor, no eligible winner causes failure. Local deadline failures remain errors, and future linearizable reads must fail when freshness cannot be established. The [configuration example](decisions.md#configure-six-clients-in-us-and-eu-groups-preset-b) shows the setting.

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

## Distribution

**Who sends the write to other regions?** Distribution follows the selected backend. It does not select when a write may return success.

| Distribution | Backend | How a write reaches other regions | Who handles missed delivery? |
| --- | --- | --- | --- |
| **Redis-managed** | Active-Active | Application writes once to its local database; Redis replicates to participating regions. | Redis, through native replication and catch-up. |
| **Adapter fan-out** | Independent clusters | Adapter sends the same immutable identified update to every configured write target. | No background repair. A later same-session write distributes its current value; without another write, missed delivery can remain unrepaired indefinitely. |

Read groups do not change write targets. Reuse IDs, content, and original absolute expiry on retries; copying must not repeat business mutations. Publish a discovery candidate only after storing its snapshot. See [backends.md](backends.md) for the distribution contract.

## Write behavior

**When can the write return success, and with what ordering guarantee?** Choose acknowledgment separately from distribution. Linearizable commit additionally requires a matching read/write protocol.

| Write behavior | Backend | Success acknowledged when | Ordering / visibility guarantee | Write latency | Status |
| --- | --- | --- | --- | --- | --- |
| **Local acknowledgment** / `local` | Independent, or Active-Active (causal consistency on or off) | The origin accepts the update under the selected durability policy. | Remote regions may lag. The acknowledgment alone adds no global ordering; native causal order applies only when Active-Active causal consistency is enabled. | **fast** | Baseline. No application replay capture or worker. |
| **All-target acknowledgment** / `all-targets` | Independent clusters | Every target in the captured write set verifies the same identified update. | Placement at acknowledgment; not atomic visibility, disk durability, or linearizability. | **slow+** | Proposed independent option; one missing target prevents success. |
| **Linearizable commit protocol** | Active-Active + custom coordination, or independent clusters + custom coordination | A future protocol establishes a safely ordered commit according to its authority/failure model. Exact commit rule remains unselected. | Target: the same real-time per-key guarantee for both linearizable implementations. Matching reads must use that protocol too. | **slow++** | Proposed/deferred; neither replication nor all-target placement alone provides it. |

Local acknowledgment is the baseline under either backend; an adapter all-target acknowledgment overlay for Active-Active is not specified. All-targets is available as a proposed independent-cluster option. The custom commit row is a future protocol responsibility, not an additional implemented `acknowledgment` value.

A write deadline does not mean null, rollback, or success. Report partial/uncertain outcomes, retain original IDs and the captured target set for reconciliation, and never silently remove an unreachable target. A later successful write does not retroactively acknowledge an earlier uncertain one. All-target placement alone provides neither linearizability nor atomic visibility or disk durability. The monotonic read modifier adds no write acknowledgment mode. See [backends.md](backends.md).

## Recovery

**What happens when delivery is incomplete?** Here, recovery means completing missed inter-region delivery. Local Redis HA, restart/restore, and persistence remain separate operational concerns.

| Recovery | Backend | After incomplete delivery | Requires another write? |
| --- | --- | --- | --- |
| **No background repair** | Independent clusters | Bounded request-time fan-out; no persisted unfinished delivery obligations. Each later same-session write distributes its current value as normal write behavior. Without another write, a missed delivery can remain unrepaired indefinitely. | **Yes**, for another delivery attempt after the request ends. |
| **Redis-managed** | Active-Active | Redis handles replication and catch-up under its configured persistence/recovery behavior. No application replay worker is added. | **No**, for Redis-managed replication recovery. |

Each later independent same-session write distributes its current version as normal write fan-out. This is not a next-write recovery setting and need not restore missed historical versions. Writes to other sessions do not repair this session. There is no application outbox, durable replay option, or background repair worker in production scope.

Active-Active supplies eventual CRDT convergence through its native transport. Independent fan-out has no unconditional eventual-convergence guarantee after missed delivery: without another write, regions may differ indefinitely. “Eventual” describes convergence when delivery completes; it does not make independent clusters replicate automatically.

Backend delivery recovery does not create linearizability. Both future linearizable protocols must separately define authority, safe commit/read rules, fencing, failover, and recovery. The independent no-background-repair baseline does not remove those future protocol obligations.

## What remains open

The baseline design selects Available/Local, bounded fan-out, and local acknowledgment; it does not implement them as a production adapter. **Use Redis Enterprise capabilities and existing client facilities as provided.** Select a compatible existing client and record the deployed Redis version and supported commands. Use native data-type/conflict semantics, configured persistence and durability, expiration, eviction/capacity controls, and client connection pools/timeouts. These are deployment and integration choices, not requests to build replacement features.

Keep adapter code limited to the selected behavior: local lookup, concurrent Available group reads with a shared deadline and cleanup, independent write fan-out, and optional all-target verification, with the necessary validation and retry identity handling. Use deployment-configured groups and existing client limits; do not add dynamic group management, a custom conflict-resolution engine, persistence layer, clock/skew-correction system, resource-management framework, or service-level enforcement subsystem. Record native limitations and measure outcomes rather than promising stronger guarantees.

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
