# Plan: multi-region session adapter

Date: 2026-11-09. Status: proposed implementation plan for the agreed RYOW target.

## Starting point and dependencies

The repository has design documents only. Language, client, middleware, provisioning, and CI are unselected. The paths below are logical proposals; add file extensions and executable commands once the stack is chosen. Resolve blockers in [sources.md](sources.md), especially lineage sequencing, successor proof, context transport, and durability.

## Order of work

1. **Finalize the contract.** Review spec.md, choose backend/acknowledgment/recovery combinations, and agree payload size, deadlines, clock-skew policy, context lifetime, retention, and service levels. Do not infer a durable-replay default.
2. **Provision representative environments.** Add `infra/README.md` and configuration for the pinned Redis Software 8.x builds, three primary shards per regional database, replicas, persistence, and endpoints. Validate V01 for each supported mode.
3. **Implement common primitives.** Add `src/config/`, `src/clients/`, `src/topology/`, and `src/records/`: validated configuration, pooled connections, immutable full envelopes, identity/digest checks, generation/expiry, and typed outcomes.
4. **Implement context and lineage.** Add `src/context/` and `src/middleware/`. Prove write serialization and response ordering; implement protected context issuance for the same caller across requests/regions. Use A1/A2 in us-west-2, B1 in us-east-1, and C1 in us-east-2, with separate contexts. Do not build or assume cross-client handoff. Cover V02, V06, V08–V10, and V18.
5. **Implement distribution before claiming regional progress.** Add `src/distribution/` for independent fan-out and next-write refresh. If enabled, add `src/outbox/` and replay-worker deployment with reviewed atomic capture, per-target application, expiry, capacity, and catch-up. Active-Active uses native transport. Cover V21–V23.
6. **Implement read policies.** Add `src/strategies/read-your-own-writes/`: default candidate selection/proof, exact reads, any reads, bounded wait loops that recheck eligible successors, cancellation, and snapshot-missing outcomes. Cover the remaining contract cases including V24–V25 and V27–V28.
7. **Verify and measure.** Add `tests/contracts/`, `tests/integration/`, `tests/faults/`, and `benchmarks/`. Run each applicable scenario on real instances of every supported configuration. Publish sanitized evidence and numeric performance results, with a single verification entry point and CI.
8. **Rehearse operations.** Replace proposed procedures in operations.md with actual staging-tested commands; update CLAUDE.md. Validate restore, partial-outcome reconciliation, topology changes, and rollback without weakening RYOW.

## Risks and completion

Highest risks are lost/rolled-back context, falsely claiming a successor relationship, missing durable capture when replay is enabled, and treating a later write as delivery of an older exact snapshot. None is solved by three shards or an eventually replicated hint.

No automatic remote read fallback, global latest discovery, strict authority, or cross-session transaction is planned. Keep this plan and the specification synchronized when scope changes. Completion needs applicable scenario evidence and accepted service levels, not merely a clean build. Documentation checks in the PR do not constitute application or infrastructure validation.
