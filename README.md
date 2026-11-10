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

| Behavior | Backend | Result | Freshness guaranteed? | Read / write latency | Implementation status |
| --- | --- | --- | --- | --- | --- |
| **Local** / `local` | Independent or Active-Active | Read only local; valid data or null. | **No.** Local data may be stale. | **Read:** one local lookup, no WAN read wait. **Write:** selected acknowledgment policy. | Proposed option. |
| **Available** / `available` | Independent or Active-Active | Race all group clusters **including local**; first valid non-null value. Null on all-null replies or deadline without a value. | **No.** The first value may be stale. | **Read:** first value, last null, or deadline; a remote winner incurs network latency. **Write:** same acknowledgment choices as Local. | **Default.** An early null does not end pending requests. |
| **Causal (Active-Active)** / `causal` | Active-Active with causal consistency enabled | Regional reads; Redis preserves causally related operation order on the same key across instances. | **No catch-up guarantee.** A region may lag while preserving causal order. | **Read:** regional lookup without a global freshness barrier. **Write:** local acknowledgment possible; causal replication adds traffic/memory/performance overhead. | Native Redis ordering feature; adapter/configuration integration proposed. Less custom ordering code than comparable independent-cluster coordination. |
| **Coordinated** / `coordinated` | Independent clusters | Proposed application coordination for linearizable-like access in the group; exact contract remains open. | **Not yet defined or guaranteed.** | **Read/write:** protocol-dependent; authority/quorum communication may add WAN round trips. | Proposed and unsupported; protocol and validation remain open. |
| **Linearizable** / `linearizable` | Active-Active required **in this project**, plus a separate coordination protocol | One real-time order per key; reads reflect writes completed before they begin. | **Yes, by contract**, within the selected scope. Not implemented. | **Read/write:** coordination may add WAN waits. No established speed advantage over Coordinated. | Deferred and unsupported; Active-Active alone does not provide this guarantee. |

For Local and Available, baseline local write acknowledgment does not wait for remote delivery; explicit independent `all-targets` waits for every captured target. Stronger modes must separately define their commit/read paths. These are qualitative latency paths, not benchmarks; see [latency.md](latency.md).

Local, Available, and Causal do not guarantee the latest completed write across regions. Causal preserves dependencies on the same key but does not prove the reader has caught up. Neither Local nor Available guarantees read-your-own-writes. Available chooses the first value, not the first reply if that reply is null. It may return older data even when another cluster has newer data. Timeout-null means no value was obtained within the deadline, not proof that the key is absent everywhere.

**Cluster-group scope**

| Scope | Membership | Effect |
| --- | --- | --- |
| **Geographic group** | US: three US regions; EU: two EU regions | Available races the selected group's members, including the caller's local cluster. A future linearizable scope would require coordination within the group. |
| **Global group** | An explicitly configured group containing all five regions | Available can race all five if that group is selected. Future global linearizability remains deferred. |

Available uses the local region's configured read group unless a valid group override is provided. Membership must include the local cluster. Read groups do not change write acknowledgment targets. **Project backend rules:** Causal requires Active-Active with causal consistency enabled; Linearizable requires Active-Active plus an additional coordination protocol; Coordinated uses independent clusters. This is an architecture/naming constraint, not a general prerequisite for linearizability. Active-Active combines strong eventual convergence with optional per-key causal ordering. That native ordering needs less custom application code than implementing comparable ordering over independent clusters. It still needs a separate validated coordination overlay for the Linearizable contract. See [consistency.md](consistency.md).

The Session read option has been removed. Production reads require no caller write context, successor proofs, or public exact-version selector. The [experimental spike](spike/README.md) retains historical controls and results; it does not implement this revised production API.

## Start here

Read [intent.md](intent.md) for the goal, [consistency.md](consistency.md) for the guarantees and examples, and [decisions.md](decisions.md) for configuration diagrams and option tradeoffs. [spec.md](spec.md) is the authoritative behavior contract.

Deployment has three separate choices:

- **Distribution:** Redis Active-Active, or independent regional databases with adapter fan-out.
- **Acknowledgment:** local by default; independent mode can explicitly wait for all configured targets.
- **Recovery in independent mode:** request-only next-write refresh, or optional durable replay.

Without durable replay, the next insert/update for the same session sends its latest version to all configured regions. It need not fill historical gaps. An absent exact snapshot is described as **snapshot missing**.

The current production implementation plan covers `available` (default) and `local`. Proposed `causal` uses native Active-Active causal ordering once adapter/configuration integration is validated; it is not a native per-request Redis read-concern setting. Proposed `coordinated` and deferred `linearizable` require separate protocols. Reject each unimplemented policy rather than silently weakening it. There is no `session`, `required`, or `greedy` public policy.

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
