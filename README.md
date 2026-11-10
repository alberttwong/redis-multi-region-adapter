# Multi-region session consistency

Design for **latest local with read-your-own-writes**, named `latest-local-ryow`, on **Redis Software 8.x**. Each regional database has **three primary data shards**, with replica shards additional. The per-region interpretation remains a sizing assumption to confirm.

## Consistency

| Consistency level | What it guarantees | Redis infrastructure and application responsibilities | Coverage in this project |
| --- | --- | --- | --- |
| **Eventual** | Regional values may differ while updates propagate, then converge when delivery completes. | **Active-Active or independent regional clusters.** Active-Active provides CRDT replication and strong eventual convergence. Independent clusters need application-managed distribution and recovery to ensure delivery. | Unprotected local reads have eventual semantics. Independent request-only delivery can leave gaps indefinitely without a later write. |
| **Read-your-own-writes (RYOW)** | A caller's dependent reads honor its acknowledged write, using carried context; unavailable required state is reported explicitly. Other callers may still see older state. | **Active-Active or independent regional clusters**, plus application-carried write context and protected-read checks. Active-Active alone does not ensure a different region has caught up to the caller's write. | **Project target: latest local + RYOW (`latest-local-ryow`).** The default returns eligible local state or waits/reports snapshot missing. |
| **Strict geographic (group-scoped linearizability)** | All callers share one per-session ordered history within a geographic group; a read after a completed write reflects it or a later committed update. | **Active-Active as the planned replication base**, plus a separately designed group-scoped authority/commit protocol, coordinated reads, fencing, and recovery. Native Active-Active replication alone does not provide this guarantee. | Deferred; no strict protocol is specified or implemented. Independent-cluster strict designs are outside the planned scope. |
| **Strict global (global linearizability)** | The same per-session ordering guarantee spans all geographic groups. | **Active-Active as the planned replication base**, plus a separately designed global authority/commit protocol, coordinated reads, fencing, and recovery across groups. Native Active-Active replication alone does not provide this guarantee. | Deferred; no strict protocol is specified or implemented. Independent-cluster strict designs are outside the planned scope. |

Active-Active is the infrastructure direction for future strict modes to avoid building regional replication and convergence ourselves; it is a project architecture choice, not a theoretical prerequisite for linearizability. Redis documents Active-Active as **strong eventual consistency**, with optional causal ordering. Neither guarantees immediate cross-region visibility after acknowledgment. See [Redis Active-Active](https://redis.io/docs/latest/operate/rs/databases/active-active/) and the [infrastructure comparison](consistency.md#infrastructure-by-consistency-level).

Independent regional clients do not exchange context or version IDs. Each client gets RYOW protection from its own writes; it cannot know another client’s unpropagated version exists. Exact-version and any-version reads are explicit alternatives; neither changes the project's consistency target. Coverage describes the production design; the experimental AWS spike exercises a subset without establishing a production guarantee. See [consistency.md](consistency.md).

## Start here

Read [intent.md](intent.md) for the goal, [consistency.md](consistency.md) for the guarantees and examples, and [decisions.md](decisions.md) for configuration diagrams and option tradeoffs. [spec.md](spec.md) is the authoritative behavior contract.

Deployment has three separate choices:

- **Distribution:** Redis Active-Active, or independent regional databases with adapter fan-out.
- **Acknowledgment:** local by default; independent mode can explicitly wait for all configured targets.
- **Recovery in independent mode:** request-only next-write refresh, or optional durable replay.

Without durable replay, the next insert/update for the same session sends its latest version to all configured regions. It need not fill historical gaps. An absent exact snapshot is described as **snapshot missing**.

Read policies are `latest` by default, explicit `required` for one exact version, and explicit `any` for any valid local candidate. None promises the latest completed update across all devices or regions.

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
