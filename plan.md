# Plan: Local and Available adapter

Date: 2026-11-09. Status: production implementation proposed; Available is default.

## Starting point

The repository contains design documents and a legacy [Python/AWS/Terraform spike](spike/README.md). Its old read controls and measurements do not implement the new group-racing Available behavior. Production SDK language, client, middleware, and CI remain unselected. Paths below are proposals.

## Order of work

1. Finalize [spec.md](spec.md), backend/acknowledgment/recovery combinations, candidate/conflict rules, allowed read groups/overrides, deadlines, concurrency, expiry, and service levels. Session context/RYOW automation is removed from scope.
2. Pin Redis Software 8.x builds, commands, clients, three primaries per regional database plus replicas, persistence, and endpoints. Keep provisioning and benchmark authorization separate from implementation work.
3. Add `src/config/`, `src/clients/`, `src/topology/`, and `src/records/`: pooled connections, immutable identity/content/expiry, valid local candidate lookup, group membership including local, and captured epochs/targets.
4. Add `src/distribution/` for idempotent independent fan-out and next-write refresh. If selected, add `src/outbox/` and a bounded replay worker with atomic capture, original expiry, per-target completion, and backpressure. Active-Active uses native transport. Preserve local versus all-target acknowledgment semantics.
5. Add `src/reads/local/` and `src/reads/available/`. Local performs one regional lookup. Default Available concurrently starts every group request including local, accepts the first valid non-null value, continues after null/failed attempts, returns null on all-null or deadline, and cleans up losers without delaying the winner. There is no public historical/version selector or client write-context path.
6. Add contract, integration, fault, and load tests following [validation.md](validation.md). Exercise first-null/later-value, stale-first wins, local wins, all-null, deadline-null, failed members, group changes, cancellation, and resource bounds against real deployments.
7. Measure Local and Available separately, including winning region, outcome rates, pending/failed attempts, pool load, and complete end-to-end histograms. Follow [latency.md](latency.md); historical spike p99 is not a prediction for the new fan-out path.
8. Rehearse expiry, uncertain-write reconciliation, restart/restore, target admission, configuration changes, rollback, and cleanup. Replace proposed operations with verified commands and sanitized evidence.

## Risks and limits

Key risks are returning null after only one miss, waiting for all members after a value wins, dispatching sequentially, accepting invalid values, unbounded fan-out/loser work, falsely claiming fresh/latest state, and shrinking write targets because a read group was selected. Neither supported read guarantees RYOW or linearizability. Future stronger-option work must specify two custom guarantees over independent clusters: Causal over Coordinated (dependency capture, transport, ordered application, recovery) and Linearizable over Coordinated (real-time write/commit/read ordering, authority, fencing/failover, bounded failure). Causal over Active-Active needs validation of native causal configuration and same-key semantics. Linearizable over Active-Active needs a separate custom protocol targeting the same full guarantee as the independent implementation. None changes the current Local/Available implementation plan, and no speed ranking is established. Current cross-device revocation and cross-session transactions remain separate designs.
