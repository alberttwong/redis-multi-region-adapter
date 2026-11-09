# Multi-region session consistency

Design for **latest local with read-your-own-writes**, named `latest-local-ryow`, on **Redis Software 8.x**. Each regional database has **three primary data shards**, with replica shards additional. The per-region interpretation remains a sizing assumption to confirm.

## Consistency

The default is **latest local + RYOW**: return locally known state that honors the caller's last acknowledged write, or report **snapshot missing** after bounded waiting. The requirement follows authenticated caller context; other devices can still see older local state. Explicit reads can request one exact version or accept any valid local version. This does not provide strict geographic or global consistency. See [consistency.md](consistency.md).

## Start here

Read [intent.md](intent.md) for the goal, [consistency.md](consistency.md) for the guarantees and examples, and [decisions.md](decisions.md) for configuration diagrams. [spec.md](spec.md) is the authoritative behavior contract.

Deployment has three separate choices:

- **Distribution:** Redis Active-Active, or independent regional databases with adapter fan-out.
- **Acknowledgment:** local by default; independent mode can explicitly wait for all configured targets.
- **Recovery in independent mode:** request-only next-write refresh, or optional durable replay.

Without durable replay, the next insert/update for the same session sends its new complete snapshot to all configured regions again. It need not fill historical gaps. An absent exact snapshot is described as **snapshot missing**.

Read policies are `latest` by default, explicit `required` for one exact version, and explicit `any` for any valid local candidate. None promises the latest completed update across all devices or regions.

## Supporting documents

- [backends.md](backends.md): distribution, acknowledgment, and recovery obligations.
- [validation.md](validation.md): requirements mapped to proposed acceptance scenarios.
- [plan.md](plan.md): implementation order, proposed paths, and completion evidence.
- [operations.md](operations.md): deployment, failure handling, and monitoring.
- [REVIEW.md](REVIEW.md): review priorities and severity.
- [CLAUDE.md](CLAUDE.md): concise implementation-session context.
- [sources.md](sources.md): provenance, selected decisions, assumptions, and open questions.

## Status

Design documents only, updated 2026-11-09. No adapter, worker, infrastructure, application tests, or enforcement hooks exist yet. The consistency target is agreed; detailed algorithms, exact builds, capacity, durability, retention, and service levels remain to be reviewed. No independent recovery combination has been selected.

The artifact structure follows the [AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook). Repository Markdown is the design source of truth; external sources supply provenance and product capability evidence.
