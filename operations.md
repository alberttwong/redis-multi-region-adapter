# Operating Local and Available reads

Status: proposed production requirements. The [legacy AWS spike](spike/README.md) has separate controls and measured runs. See [spec.md](spec.md) and [backends.md](backends.md).

## Configuration and scope

Record exact Redis Software/client builds, three primaries per regional database plus replicas, persistence, expiry, capacity, local endpoint, allowed groups, default read group, shared read deadline, and concurrency/pool limits. US has three regional clusters; EU two; global is explicit. Available groups must include local and resolve to distinct known endpoints. Six clients on five databases do not mean six targets.

Default policy is `available`; explicit `local` reads only local. Capture membership/epoch at dispatch. Reject malformed or unauthorized groups before sending reads. Read groups do not shrink captured all-target write obligations or add a foreign-group wait to local write acknowledgment.

## Read outcomes

Available concurrently queries every group member including local. Return first valid non-null value immediately; continue past null replies, failed probes, and rejected candidates. Return null on all-null completion or shared deadline without a value. Do not block a winner on loser cleanup. Cancel/discard losing or late work without leaking connections, workers, or callbacks.

A stale first value is permitted. A deadline-null may occur when a value exists in a slow/unreachable cluster. Record winner, all-null, deadline-null, failed/rejected attempts, and late replies separately. Keep request-level access/configuration failures as errors. Local returns value/null for one endpoint, with infrastructure and integrity errors distinct; it has no automatic remote fallback.

Local/Available require no caller-history floor. Proposed Monotonic requires automatic last-successful-read history, never an explicit business-code version selector; if its established floor is unavailable, wait/fail rather than return older state or timeout-null. Session, Causal, and public exact-version read paths remain removed. Internal write-placement checks may still identify an expected copy as **snapshot missing**; this is not the public Available timeout contract. Keep raw payloads, bearer IDs, and credentials out of logs.

## Writes and recovery

Independent request-only distributes the next same-session update's latest version and need not restore missing history. Idle regions can remain stale indefinitely. Optional durable replay must capture obligations before success, retain original expiry, retry idempotently, and apply backpressure before obligations are lost. Monitor backlog, oldest work, per-target progress, and expiry.

Local acknowledgment accepts the origin; explicit independent all-target success requires every captured target. Timeout is partial/uncertain, not rollback. Preserve original IDs and targets for reconciliation; a later write does not retroactively acknowledge an earlier one. Read groups and write participant sets remain separate.

## Restore, rollout, and evidence

Restored/admitted targets need backend-specific readiness, integrity/expiry checks, and any selected replay catch-up protocol. Healthy connectivity does not prove freshness. Request-only admission has no historical-backfill promise. Preserve epochs and outstanding write obligations during changes.

Measure Local and Available at realistic group size/load, including null/error rates, all-attempt histograms, per-target latency, pool saturation, fan-out counts, cancellations, and late work. Rehearse first-null/later-value, all-null, deadline-null, stale-first, partial endpoint failure, membership changes, and winner cleanup. Rollout/rollback must preserve the documented policy behavior; no production release automation is installed by these documents.

Active-Active provides eventual convergence. Linearizable coordination and immediate cross-device revocation remain separate deferred designs; neither a racing read nor all-target placement establishes them.
