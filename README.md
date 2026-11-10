# Multi-region session consistency

Design for **Session reads with read-your-own-writes (RYOW)**, named `session`, on **Redis Software 8.x**. Each regional database has **three primary data shards**, with replica shards additional. The per-region interpretation remains a sizing assumption to confirm.

## Consistency

The tables separate convergence, read consistency, and cluster-group scope. Eventual convergence can coexist with Session reads. Defining a group alone does not enforce linearizability.

**How regional copies converge**

| Convergence guarantee | Meaning | Coverage in this project |
| --- | --- | --- |
| **Eventual** | Regional values may differ during propagation, then converge when delivery completes. | Active-Active supplies replication. Independent clusters need adapter fan-out and recovery; request-only delivery can leave gaps indefinitely without a later write. |

**Read behavior / consistency guarantee**

| Read behavior / guarantee | Meaning | Redis infrastructure and application responsibilities | Coverage in this project |
| --- | --- | --- | --- |
| **Available** / `available` | Return valid local data or not found, without waiting for remote updates. May miss completed writes. | Active-Active or independent clusters; local candidate validation and access checks. | Explicit `available` policy. |
| **Session (RYOW)** / `session` | Reflect the caller's own acknowledged write or a proven successor. Other callers may see older state. | Either backend, plus protected caller context, successor proof, and local wait/error handling. Active-Active alone does not ensure RYOW across regions. | **Selected default:** `session`. |
| **Linearizable** / `linearizable` (deferred) | One ordered history per session key, respecting real-time operation order, for every caller in the selected scope. | Active-Active as the planned replication base, plus a separate authority/commit protocol, coordinated reads, fencing, and recovery. | Deferred; no protocol is specified or implemented. Independent-cluster linearizable designs are outside planned scope. |

For Session and linearizable reads, unavailable required state causes waiting or an explicit failure, not stale success. Session is a proposed SDK behavior: middleware must automatically retain write context and attach it to dependent reads. The current spike explicitly manages context and does not implement that SDK automation. Session names this project's RYOW behavior; it does not imply MongoDB's full causal consistency guarantees. These are the project's guarantee labels, not an exhaustive consistency taxonomy.

**Cluster-group scope for a linearizable guarantee**

| Scope | Covered clusters and callers | Combined guarantee |
| --- | --- | --- |
| **Geographic group** | A configured group, such as the three US regions or the two EU regions | **Linearizable geographic:** shared ordering within that group; other groups may lag. |
| **Global** | All five regions across both groups | **Linearizable global:** shared ordering across all regions. |

Group membership is topology metadata. Neither linearizable scope is supported in this phase. Session reads follow caller context across groups; this behavior is not restricted to a geographic group. Group names do not change acknowledgment targets.

Active-Active is the planned infrastructure direction for future linearizable behavior to reduce custom replication code. It is not a theoretical prerequisite for linearizability and does not supply it alone. See the [infrastructure comparison](consistency.md#infrastructure-by-consistency-level).

Independent regional clients do not exchange context or version IDs. Each client gets RYOW protection from its own writes; it cannot know another client’s unpropagated version exists. Available reads are an explicit alternative. Exact-version lookup is internal plumbing for Session reads, not a public read policy. Coverage describes the production design; the experimental AWS spike exercises a subset without establishing a production guarantee. See [consistency.md](consistency.md).

## Start here

Read [intent.md](intent.md) for the goal, [consistency.md](consistency.md) for the guarantees and examples, and [decisions.md](decisions.md) for configuration diagrams and option tradeoffs. [spec.md](spec.md) is the authoritative behavior contract.

Deployment has three separate choices:

- **Distribution:** Redis Active-Active, or independent regional databases with adapter fan-out.
- **Acknowledgment:** local by default; independent mode can explicitly wait for all configured targets.
- **Recovery in independent mode:** request-only next-write refresh, or optional durable replay.

Without durable replay, the next insert/update for the same session sends its latest version to all configured regions. It need not fill historical gaps. An absent exact snapshot is described as **snapshot missing**.

Public read policies are `session` (default) and `available`. Session supplies RYOW, not the latest completed write across all callers. `linearizable` describes a deferred behavior and is rejected as unsupported in this phase. Expected snapshot/version identifiers stay in protected middleware context; exact-version lookup is internal plumbing.

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

Design plus an experimental AWS/Terraform latency spike, updated 2026-11-09. The spike has prototype read/write/replay paths and protocol tests; it is not a production adapter or strict consistency implementation. No production enforcement hooks exist yet. The consistency target is agreed; detailed algorithms, exact builds, capacity, durability, retention, and service levels remain to be reviewed. No independent recovery combination has been selected.

The artifact structure follows the [AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook). Repository Markdown is the design source of truth; external sources supply provenance and product capability evidence.
