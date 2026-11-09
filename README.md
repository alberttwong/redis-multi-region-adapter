# Multi-region session consistency

Design for **latest local with read-your-own-writes**, named `latest-local-ryow`, on **Redis Software 8.x**. Each regional database has **three primary data shards**, with replica shards additional. The per-region interpretation remains a sizing assumption to confirm.

## Consistency

| Consistency level | What it guarantees | Coverage in this project |
| --- | --- | --- |
| **Eventual** | Regional values may differ while updates propagate, then converge when delivery completes. | Replication foundation in Active-Active; unprotected local reads have eventual semantics. Independent request-only delivery can leave gaps until a later write. |
| **Read-your-own-writes (RYOW)** | A caller's dependent reads honor its acknowledged write, using carried context; unavailable required state is reported explicitly. Other callers may still see older state. | **Project target: latest local + RYOW (`latest-local-ryow`).** The default returns eligible local state or waits/reports snapshot missing. |
| **Strict geographic** | All callers share one per-session ordered history within a geographic group; a read after a completed write reflects it or a later committed update. | Not covered; requires additional commit ordering, coordinated reads, fencing, and recovery. |
| **Strict global** | The same per-session ordering guarantee spans all geographic groups. | Not covered; requires coordination across groups. |

The requirement follows authenticated caller context. Exact-version and any-version reads are explicit alternatives; neither changes the project's consistency target. This is a design-only repository, so coverage describes intended behavior rather than an implemented guarantee. See [consistency.md](consistency.md).

## Start here

Read [intent.md](intent.md) for the goal, [consistency.md](consistency.md) for the guarantees and examples, and [decisions.md](decisions.md) for configuration diagrams and option tradeoffs. [spec.md](spec.md) is the authoritative behavior contract.

Deployment has three separate choices:

- **Distribution:** Redis Active-Active, or independent regional databases with adapter fan-out.
- **Acknowledgment:** local by default; independent mode can explicitly wait for all configured targets.
- **Recovery in independent mode:** request-only next-write refresh, or optional durable replay.

Without durable replay, the next insert/update for the same session sends its latest version to all configured regions. It need not fill historical gaps. An absent exact snapshot is described as **snapshot missing**.

Read policies are `latest` by default, explicit `required` for one exact version, and explicit `any` for any valid local candidate. None promises the latest completed update across all devices or regions.

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

Design documents only, updated 2026-11-09. No adapter, worker, infrastructure, application tests, or enforcement hooks exist yet. The consistency target is agreed; detailed algorithms, exact builds, capacity, durability, retention, and service levels remain to be reviewed. No independent recovery combination has been selected.

The artifact structure follows the [AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook). Repository Markdown is the design source of truth; external sources supply provenance and product capability evidence.
