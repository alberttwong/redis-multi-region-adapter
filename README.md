# Multi-region session consistency

**Available reads by default.**

The design targets Redis Software 8.x. Each regional database has three primary data shards, with replicas additional. The per-region sizing interpretation remains an assumption to confirm.

## Consistency

Propagation, read behavior, and cluster-group scope are separate choices.

**How regional copies converge**

| Convergence | Meaning | Infrastructure |
| --- | --- | --- |
| **Eventual** | Copies may differ during delivery and converge when delivery completes. | Active-Active owns replication; independent clusters need adapter fan-out/recovery. Request-only delivery can leave gaps indefinitely without a later write. |

**Read behavior**

| Behavior | Backend | Result | Ordering | Freshness guaranteed? | Read / write latency | Implementation status |
| --- | --- | --- | --- | --- | --- | --- |
| **Local** / `local` | Independent or Active-Active | Read only local; valid data or null. | No cross-region ordering guarantee. | **No.** Local data may be stale. | **Read:** fast. **Write:** fast. | Proposed option. |
| **Available** / `available` | Independent or Active-Active | Race all group clusters **including local**; first valid non-null value. Null on all-null replies or deadline without a value. | No cross-region ordering guarantee; first value by reply arrival. | **No.** The first value may be stale. | **Read:** slow. **Write:** fast. | **Default.** An early null does not end pending requests. |
| **Causal over Active-Active** / `causal` | Active-Active with causal consistency enabled | Regional reads with Redis preserving causal dependencies on the same key. | Same-key causal order, native to Redis; no custom ordering protocol. | **No catch-up guarantee.** A region may lag. | **Read:** fast. **Write:** fast. | Native ordering; adapter/configuration integration proposed. |
| **Causal over Coordinated** / `causal-coordinated` | Independent clusters + custom coordination | Target: preserve causal dependencies on the same key across group members. | Same-key causal order, enforced by a custom dependency/replication protocol. | **No catch-up guarantee.** Causal order allows stale regional reads. | **Read:** slow+. **Write:** slow+. | Proposed and unsupported; protocol remains unimplemented. |
| **Linearizable over Active-Active** / `linearizable` | Active-Active + custom coordination | One real-time order per key; reads reflect writes completed before they begin. | Real-time ordering per key within scope; custom coordination required. | **Yes, by contract**, within scope. Not implemented. | **Read:** slow+. **Write:** slow+. | Deferred; Active-Active alone does not provide linearizability. |
| **Linearizable over Coordinated** / `linearizable-coordinated` | Independent clusters + custom coordination | Same linearizable contract, implemented through an independent-cluster coordination protocol. | Real-time ordering per key within scope; custom coordination required. | **Yes, by contract**, within scope. Not implemented. | **Read:** slow+. **Write:** slow+. | Proposed and unsupported; ordering/commit/read/failover protocol remains unimplemented. |

Latency labels are planning estimates, not measurements: **fast** = regional path; **slow** = remote-response path; **slow+** = coordination across regions; **slow++** = extra sequential WAN coordination or a deadline wait. Local write acknowledgment is assumed where supported. Available can be fast when local wins or slow++ at timeout. Custom coordination ratings are provisional assumptions, not inherent costs of a guarantee; a causal protocol may replicate asynchronously, and final read/write paths are unselected. No speed ranking between the linearizable implementations is established. See [latency.md](latency.md).

The causal options target the same **per-key causal ordering**, but only Active-Active supplies that ordering natively. The linearizable options target the same **real-time freshness and ordering per key**, using different backends. All custom coordination protocols require design and validation; choosing a label does not implement the guarantee.

Local, Available, and both causal options do not guarantee the latest completed write across regions. Causal ordering preserves dependencies without proving a reader has caught up. Available chooses the first value, not the first null reply; it can return an old value even when another cluster has newer data. Timeout-null is not proof of absence everywhere. Linearizable options must wait or fail if their freshness requirement cannot be established; Available's timeout-null rule does not apply to them.

**Cluster-group scope**

| Scope | Membership | Effect |
| --- | --- | --- |
| **Geographic group** | US: three US regions; EU: two EU regions | Available races the selected group's members, including the caller's local cluster. A future linearizable scope would require coordination within the group. |
| **Global group** | An explicitly configured group containing all five regions | Available can race all five if that group is selected. Future global linearizability remains deferred. |

Available uses the local region's configured read group unless a valid group override is provided. Membership must include the local cluster. Read groups do not change write acknowledgment targets. **Project backend mapping:** the “over Active-Active” options use Active-Active (causal consistency must be enabled for Causal); the “over Coordinated” options use independent clusters with custom protocols. Linearizability is the same target guarantee with either implementation. See [consistency.md](consistency.md).

The Session read option has been removed. Local/Available reads require no caller write context or successor proofs. There is no public exact-version selector. The [experimental spike](spike/README.md) retains historical controls and results; it does not implement this revised production API.

## Start here

Read [intent.md](intent.md) for the goal, [consistency.md](consistency.md) for the guarantees and examples, and [decisions.md](decisions.md) for configuration diagrams and option tradeoffs. [spec.md](spec.md) is the authoritative behavior contract.

Deployment has three separate choices:

- **Distribution:** Redis Active-Active, or independent regional databases with adapter fan-out.
- **Acknowledgment:** local by default; independent mode can explicitly wait for all configured targets.
- **Recovery in independent mode:** request-only next-write refresh, or optional durable replay.

Without durable replay, the next insert/update for the same session sends its latest version to all configured regions. It need not fill historical gaps. An absent exact snapshot is described as **snapshot missing**.

The current production implementation plan covers `available` (default) and `local`. Proposed labels are `causal`, `causal-coordinated`, `linearizable`, and `linearizable-coordinated`. They require validated adapter/configuration or custom protocol implementations before use; reject unimplemented options rather than weakening them. The ambiguous `coordinated` policy is replaced by its two explicit guarantees. Session/exact-version reads remain removed.

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
