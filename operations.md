# Operating Local and Available reads

Status: proposed production requirements. The [legacy AWS spike](spike/README.md) has separate controls and measured runs. See [spec.md](spec.md) and [backends.md](backends.md).

## Configuration and scope

Record exact Redis Software/client builds, three primaries per regional database plus replicas, persistence, expiry, capacity, local endpoint, allowed groups, default read group, shared read deadline, and concurrency/pool limits. US has three regional clusters; EU two; global is explicit. Available groups must include local and resolve to distinct known endpoints. Six clients on five databases do not mean six targets.

Default policy is `available`; explicit `local` reads only local. Capture membership/epoch at dispatch. Reject malformed or unauthorized groups before sending reads. Read groups do not shrink captured all-target write obligations or add a foreign-group wait to local write acknowledgment.

## Read outcomes

Available concurrently queries every group member including local. Return first valid non-null value immediately; continue past null replies, failed probes, and rejected candidates. Return null on all-null completion or shared deadline without a value. Do not block a winner on loser cleanup. Cancel/discard losing or late work without leaking connections, workers, or callbacks.

A stale first value is permitted. A deadline-null may occur when a value exists in a slow/unreachable cluster. Record winner, all-null, deadline-null, failed/rejected attempts, and late replies separately. Keep request-level access/configuration failures as errors. Local returns value/null for one endpoint, with infrastructure and integrity errors distinct; it has no automatic remote fallback.

Local/Available with `monotonic: false` require no caller-history floor. Proposed `monotonic: true` is an optional guarantee requiring automatic last-successful-read history, never an explicit business-code version selector; if its established floor is unavailable, wait/fail rather than return older state or timeout-null. With the modifier on, Local only waits/rechecks locally and Available filters its group race; no acceptable unexpired state means failure. Off-reads retain but do not enforce/advance the floor. Session, Causal, public exact-version, and standalone Monotonic read policies remain removed. Internal write-placement checks may still identify an expected copy as **snapshot missing**; this is not the public Available timeout contract. Keep raw payloads, bearer IDs, and credentials out of logs.

## Writes and recovery

Derive delivery recovery from the backend: independent clusters have no background repair; Active-Active uses Redis-managed replication recovery. There is no adapter recovery selector. Reject obsolete recovery configuration rather than silently accepting it.

Each independent same-session write distributes its current value as normal fan-out. Idle regions may remain stale indefinitely after incomplete delivery. No application outbox or repair worker is planned. Monitor request-time delivery outcomes, per-target failures, and expiry; Redis-managed backlog/catch-up belongs to Active-Active operations.

Local acknowledgment accepts the origin; explicit independent all-target success requires every captured target. Timeout is partial/uncertain, not rollback. Preserve original IDs and targets for reconciliation; a later write does not retroactively acknowledge an earlier one. Read groups and write participant sets remain separate.

## Restore, rollout, and evidence

Restored/admitted targets need backend-specific readiness and integrity/expiry checks. Healthy connectivity does not prove freshness. Independent targets have no historical-backfill promise; Active-Active uses native catch-up. Preserve configuration epochs and identities needed to reconcile uncertain writes.

Measure Local and Available at realistic group size/load, including null/error rates, all-attempt histograms, per-target latency, pool saturation, fan-out counts, cancellations, and late work. Rehearse first-null/later-value, all-null, deadline-null, stale-first, partial endpoint failure, membership changes, and winner cleanup. Rollout/rollback must preserve the documented policy behavior; no production release automation is installed by these documents.

For future linearizable modes on either backend, use **slow++** for both read and write planning; record actual per-operation histograms separately rather than treating the label as an SLO. Active-Active provides eventual convergence. Linearizable coordination and immediate cross-device revocation remain separate deferred designs; neither a racing read nor all-target placement establishes them.

Local and Available inherit same-key causal operation ordering when Active-Active causal consistency is enabled. This backend ordering does not ensure a region has caught up or prevent a caller from reading older state after switching regions. With monotonic on, both strategies additionally enforce per-caller same-key non-regression using automatic read history; independent clusters need that enforcement too. Neither causal ordering nor monotonic reads guarantees the latest completed write. Same-key Redis ordering must not be assumed to order multiple snapshot/hint keys.
