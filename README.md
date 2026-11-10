# Multi-region session consistency

1. **Local:** Does my local cluster have a value?
2. **Available (default):** Does any cluster in my group have a value?
3. **Monotonic:** Can I read without going backward from what I have already seen?
4. **Linearizable over Active-Active:** Does this read reflect writes completed before it began, using Active-Active plus coordination?
5. **Linearizable over Coordinated:** Does this read reflect writes completed before it began, using independent clusters plus coordination?

**Available reads by default.**

The design targets Redis Software 8.x. Each regional database has three primary data shards, with replicas additional. The per-region sizing interpretation remains an assumption to confirm.

## Consistency

Propagation, read behavior, and cluster-group scope are separate choices.

**How regional copies converge**

| Convergence | Meaning | Infrastructure |
| --- | --- | --- |
| **Eventual** | Copies may differ during delivery and converge when delivery completes. | Active-Active owns replication; independent clusters need adapter fan-out/recovery. Request-only delivery can leave gaps indefinitely without a later write. |

**Read behavior**

| Behavior | Main question | Backend | Ordering | Freshness guaranteed? | Read latency | Implementation status |
| --- | --- | --- | --- | --- | --- | --- |
| **Local** / `local` | Does my local cluster have a value? | Independent, or Active-Active (causal setting on or off) | No cross-region ordering added by this read strategy. | **No.** Local data may be stale. | **fast** | **S — Proposed.** One regional lookup using shared client/validation code. |
| **Available** / `available` | Does any cluster in my group have a value? | Independent, or Active-Active (causal setting on or off) | First non-null value by reply arrival; no read-history ordering. | **No.** The first value may be stale. | **slow** | **M — Proposed default.** Concurrent group fan-out, shared deadlines, validation, and loser cleanup. |
| **Monotonic** / `monotonic` | Can I read without going backward from what I have already seen? | Independent or Active-Active, with automatic caller read-history tracking and version/history validation | Subsequent reads in a caller's tracked sequence cannot regress in the accepted per-key history. | **No latest-write guarantee.** Must honor the last-observed floor. | **slow+** | **L — Proposed, unimplemented.** Automatic read-history storage/transport, state-order proofs, concurrency safety, and bounded failure. |
| **Linearizable over Active-Active** / `linearizable` | Does this read reflect writes completed before it began? | Active-Active + custom coordination | One real-time order per key within scope. | **Yes, by contract**, within scope. Not implemented. | **slow+** | **XL — Deferred, unimplemented.** Custom ordering/commit/read protocol, fencing/failover, and fault validation; Active-Active supplies replication only. |
| **Linearizable over Coordinated** / `linearizable-coordinated` | Does this read reflect writes completed before it began? | Independent clusters + custom coordination | The same real-time order per key within scope. | **Yes, by contract**, within scope. Not implemented. | **slow+** | **XL — Proposed, unimplemented.** Custom ordering/commit/read and independent-cluster recovery/failover protocol with fault validation. |

Effort sizes are rough relative implementation estimates: **S** = small, bounded feature; **M** = moderate concurrency/resource handling; **L** = substantial cross-request state and correctness work; **XL** = distributed protocol and failure/recovery validation. They include feature integration and relevant tests, assuming shared clients, authorization, record validation, and topology plumbing exist. They exclude infrastructure deployment and a complete production SDK. Monotonic and linearizable estimates have low confidence until history/protocol designs are chosen; either may grow. Linearizable read/write work is shared, so these sizes are not additive or delivery-date commitments.

Latency labels are planning estimates: **fast** = regional path; **slow** = remote-response path; **slow+** = history verification/coordination or freshness waiting; **slow++** = extra sequential WAN phases or a deadline wait. Available can be fast when local wins or slow++ at timeout. Monotonic can be fast if a candidate already satisfies the floor, or slow++ if it reaches its deadline. Final protocols may change the ratings; no speed ranking between the linearizable implementations is established. See [latency.md](latency.md).

Available returns the first valid non-null value from the group including local; an early null does not stop pending requests. Monotonic proposes the same group race filtered by automatically carried read history: after observing 42, it may return 42 or a proven later state, but not older 41. It may miss newest 43, so it is not linearizable. Raw version numbers or unrelated record IDs alone do not prove history order.

Local/Available can return stale data or null after a completed write. Available timeout-null does not prove absence everywhere. A Monotonic read with an established unexpired floor must wait/fail if no acceptable state is found, rather than return an older value or timeout-null. Either linearizable implementation must similarly wait/fail when it cannot establish real-time freshness.

**Cluster-group scope**

| Scope | Membership | Effect |
| --- | --- | --- |
| **Geographic group** | US: three US regions; EU: two EU regions | Available races the selected group's members, including the caller's local cluster. A future linearizable scope would require coordination within the group. |
| **Global group** | An explicitly configured group containing all five regions | Available can race all five if that group is selected. Future global linearizability remains deferred. |

Available uses the local region's configured read group unless a valid group override is provided. Membership must include the local cluster. Read groups do not change write acknowledgment targets. **Project backend mapping:** Local, Available, and proposed Monotonic can use either backend. Monotonic requires automatic read-history enforcement on both; native Active-Active causal ordering does not provide cross-region caller monotonicity by itself. The two linearizable options retain their named backends and custom coordination requirements. See [consistency.md](consistency.md).

Session and Causal read options have been removed. Monotonic tracks successful reads rather than promising read-your-own-writes. Local/Available require no caller-history floor. There is no public exact-version selector. The [experimental spike](spike/README.md) retains historical controls and results; it does not implement this revised production API.

## Write behavior

This table describes acknowledgment/commit behavior. Distribution and recovery are separate choices; Available is a read policy, not a write acknowledgment mode.

| Write behavior | Backend | Success acknowledged when | Ordering / visibility guarantee | Write latency | Status |
| --- | --- | --- | --- | --- | --- |
| **Local acknowledgment** / `local` | Independent, or Active-Active (causal consistency on or off) | The origin accepts the update under the selected durability policy; independent durable replay also captures its obligation before success. | Remote regions may lag. The acknowledgment alone adds no global ordering; native causal order applies only when Active-Active causal consistency is enabled. | **fast** | Baseline. Replay capture adds work when enabled. |
| **All-target acknowledgment** / `all-targets` | Independent clusters | Every target in the captured write set verifies the same identified update. | Placement at acknowledgment; not atomic visibility, disk durability, or linearizability. | **slow+** | Proposed independent option; one missing target prevents success. |
| **Linearizable commit protocol** | Active-Active + custom coordination, or independent clusters + custom coordination | A future protocol establishes a safely ordered commit according to its authority/failure model. Exact commit rule remains unselected. | Target: the same real-time per-key guarantee for both linearizable implementations. Matching reads must use that protocol too. | **slow+** | Proposed/deferred; neither replication nor all-target placement alone provides it. |

Latency labels are planning estimates; capture overhead, additional WAN phases, or deadlines can change the band. A timed-out all-target or custom commit is not success or rollback: preserve IDs and report the protocol's partial/uncertain/error outcome. Do not apply Available reads' timeout-null behavior to writes. The custom commit row is a future protocol responsibility, not an implemented `acknowledgment` value. Monotonic is a read-only guarantee and does not add a write acknowledgment mode or advance its floor from writes alone.

**Distribution:** write once with Active-Active and let Redis replicate, or copy the same immutable update to the configured independent clusters. **Independent recovery:** request-only next-write refresh, or optional durable replay. These choices do not change merely because a read group or read policy is selected. See [backends.md](backends.md).

## Start here

Read [intent.md](intent.md) for the goal, [consistency.md](consistency.md) for the guarantees and examples, and [decisions.md](decisions.md) for configuration diagrams and option tradeoffs. [spec.md](spec.md) is the authoritative behavior contract.

Deployment has three separate choices:

- **Distribution:** Redis Active-Active, or independent regional databases with adapter fan-out.
- **Acknowledgment:** local by default; independent mode can explicitly wait for all configured targets.
- **Recovery in independent mode:** request-only next-write refresh, or optional durable replay.

Without durable replay, the next insert/update for the same session sends its latest version to all configured regions. It need not fill historical gaps. An absent exact snapshot is described as **snapshot missing**.

The current production baseline covers `available` (default) and `local`. Proposed `monotonic` needs automatic caller read-history storage/transport and reliable state-order validation; both linearizable variants need custom protocols. Reject unimplemented/removed policies rather than silently weakening them. Causal consistency remains an optional native Active-Active backend setting, not a public read behavior or custom causal protocol workstream. It preserves same-key dependencies without guaranteeing caught-up reads. See [backends.md](backends.md#backend-causal-consistency-setting).

## AWS latency spike

[spike/README.md](spike/README.md) documents the Terraform deployment, experimental regional runners, preset A–E measurements, and reproduction/teardown steps. It targets the latest verified Redis Software build, pinned to 8.2.6-25. The production session SDK and strict geographic protocol remain unimplemented.

## Supporting documents

- [backends.md](backends.md): distribution, acknowledgment, and recovery obligations.
- [latency.md](latency.md): p99 estimation by configuration, read path, and outcome.
- [validation.md](validation.md): requirements mapped to proposed acceptance scenarios.
- [plan.md](plan.md): implementation order, proposed paths, and completion evidence.
- [operations.md](operations.md): deployment, failure handling, and monitoring.
- [REVIEW.md](REVIEW.md): review priorities and severity.
- [CLAUDE.md](CLAUDE.md): concise implementation-session context.
- [sources.md](sources.md): provenance, selected decisions, assumptions, and open questions.

## Status

Design plus an experimental AWS/Terraform latency spike, updated 2026-11-09. The spike has prototype read/write/replay paths and protocol tests; it is not a production adapter or strict consistency implementation. No production enforcement hooks exist yet. The consistency target is agreed; detailed algorithms, exact builds, capacity, durability, retention, and service levels remain to be reviewed. No independent recovery combination has been selected. Group-racing Available is a revised production design; the legacy spike does not implement it.

The artifact structure follows the [AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook). Repository Markdown is the design source of truth; external sources supply provenance and product capability evidence.
