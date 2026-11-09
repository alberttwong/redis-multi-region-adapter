# Plan: read-your-own-writes adapter

Date: 2026-11-09

Status: RYOW target selected; implementation plan proposed

Inputs: [intent.md](intent.md), [spec.md](spec.md)

## Baseline

The repository contains documentation only. Language, client, CI, provisioning, and executable verification commands remain unresolved. Paths below are proposed logical locations; add extensions once the stack is chosen.

## Sequence

| Step | Work and proposed files | Proof |
| --- | --- | --- |
| 1 | Resolve SDK language, context transport/security, token size, retention, local durability, local hint publication/generation rules, descendant/incorporation proof, and freshness deadlines in spec.md and sources.md | Reviewed RYOW contract and bounded scope |
| 2 | Add `infra/README.md` and provisioning configuration for pinned Redis Software 8.x Active-Active, three primary shards per regional instance, replicas, and persistence | V01 deployed configuration readback |
| 3 | Add `src/config/`, `src/clients/`, `src/records/`, and `src/topology/` | Envelope/configuration tests; pooled clients; exact-ID lookup |
| 4 | Add `src/context/` and `src/middleware/` for protected context issuance, cross-device handoff, propagation, and caller sequencing | V02, V06, V08, V09 |
| 5 | Add `src/strategies/read-your-own-writes/` for required exact-snapshot checks, bounded waiting, explicit freshness errors, default latest-local candidate validation, and opt-in any-version local hint reads | V03–V05, V07, V10 |
| 6 | Add `tests/contracts/`, `tests/integration/`, and `tests/faults/` using real Active-Active regional instances | V01–V14 and V16–V20 with reproducible delays, response loss, expiry, and restore |
| 7 | Add `benchmarks/` and a single verification entry point; wire CI | V15 measured results against accepted targets |
| 8 | Update operations.md and CLAUDE.md with actual run/recovery commands and staging evidence | Rollout and rollback rehearsal |

## Risks

Lost context can silently destroy RYOW if middleware treats it as an ordinary eventual read. Concurrent requests can overwrite a caller's newer context with an older response. Expiry, eviction, and data loss can make the required snapshot unavailable. Active-Active local conditional writes do not provide global idempotency for arbitrary mutations. Use immutable, uniquely identified snapshots and constrain retry routing.

The current proposal waits at the selected endpoint and returns a freshness error at deadline. Remote fallback, mutable latest-state discovery, global conflict ordering, L2 barriers, and S1 authority are excluded from this implementation phase.

## Verification

Use [validation.md](validation.md). A single-node substitute cannot certify Active-Active behavior. Preserve sanitized operation histories, topology, fault schedule, product build, and outcomes. Keep plan.md and spec.md synchronized with implementation deviations. Application tests and infrastructure provisioning are outside this documentation change. Record the actual documentation validation and submission evidence in the PR.
