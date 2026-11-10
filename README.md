# Multi-region session consistency

Design for **Available reads by default** (`available`) and explicit **Local reads** (`local`) on **Redis Software 8.x**. Each regional database has three primary data shards, with replicas additional. The per-region sizing interpretation remains an assumption to confirm.

## Consistency

Propagation, read behavior, and cluster-group scope are separate choices.

**How regional copies converge**

| Convergence | Meaning | Infrastructure |
| --- | --- | --- |
| **Eventual** | Copies may differ during delivery and converge when delivery completes. | Active-Active owns replication; independent clusters need adapter fan-out/recovery. Request-only delivery can leave gaps indefinitely without a later write. |

**Read behavior**

| Behavior | Result | Implementation status |
| --- | --- | --- |
| **Local** / `local` | Read only the local cluster; return valid data or null. Redis Active-Active handles propagation, or the adapter handles it for independent clusters. | Proposed explicit option; no freshness guarantee. |
| **Available** / `available` | Query every cluster in the selected group concurrently, **including local**. Return the first valid non-null value; return null when all replies are null or the deadline expires without a value. | **Default.** Remote null replies do not end the race while other requests are pending. |
| **Linearizable** / `linearizable` | Reflect completed writes in one real-time order per key within the selected scope. | Deferred and unsupported; requires a separately designed coordination protocol. |

Neither Local nor Available guarantees the newest value or read-your-own-writes. Available chooses the first value, not the first reply if that reply is null. It may return older data even when another cluster has newer data. Timeout-null means no value was obtained within the deadline, not proof that the key is absent everywhere.

**Cluster-group scope**

| Scope | Membership | Effect |
| --- | --- | --- |
| **Geographic group** | US: three US regions; EU: two EU regions | Available races the selected group's members, including the caller's local cluster. A future linearizable scope would require coordination within the group. |
| **Global group** | An explicitly configured group containing all five regions | Available can race all five if that group is selected. Future global linearizability remains deferred. |

Available uses the local region's configured read group unless a valid group override is provided. Membership must include the local cluster. Read groups do not change write acknowledgment targets. Active-Active provides strong eventual convergence, not linearizability; its possible use as the replication base of a linearizable design is unvalidated. See [consistency.md](consistency.md).

The Session read option has been removed. Production reads require no caller write context, successor proofs, or public exact-version selector. The [experimental spike](spike/README.md) retains historical controls and results; it does not implement this revised production API.

## Start here

Read [intent.md](intent.md) for the goal, [consistency.md](consistency.md) for the guarantees and examples, and [decisions.md](decisions.md) for configuration diagrams and option tradeoffs. [spec.md](spec.md) is the authoritative behavior contract.

Deployment has three separate choices:

- **Distribution:** Redis Active-Active, or independent regional databases with adapter fan-out.
- **Acknowledgment:** local by default; independent mode can explicitly wait for all configured targets.
- **Recovery in independent mode:** request-only next-write refresh, or optional durable replay.

Without durable replay, the next insert/update for the same session sends its latest version to all configured regions. It need not fill historical gaps. An absent exact snapshot is described as **snapshot missing**.

Public read policies are `available` (default) and `local`. `linearizable` is deferred and rejected as unsupported. There is no `session`, `required`, or `greedy` public policy.

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
