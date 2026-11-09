# Review guidance

Review [intent.md](intent.md), [spec.md](spec.md), [plan.md](plan.md), and [validation.md](validation.md).

## Passes

1. RYOW correctness: trace write acknowledgment through context issuance, middleware propagation, destination read, snapshot validation, and deadline failure. Check both stale hits and misses.
2. Caller lifecycle: check response reordering, concurrent writes, retries after response loss, lost/forged context, generation changes, and expiry.
3. Security and operations: check token binding, authorization boundaries, logging, pooled clients, topology refresh, restore, and the exact Redis Software 8.x Active-Active three-primary-shard configuration.

Reject successful protected reads that return older state, convert an expected unexpired record's absence into `null`, or drop context and silently use eventual reads. Require evidence from real Active-Active instances. Do not claim global idempotency from a local conditional command or latest-state/revocation protection from RYOW.

Review all three policies. Default `latest` requires local candidate plus verified incorporation of caller context, falling back to the required snapshot or error. Test omitted-policy behavior and incomparable concurrent lineages. Explicit policies: `required` must return the exact requested identity, while `any` may return older/newer local state or `null`. Check actual-version metadata, hint integrity/expiry and generation handling, authenticated Device B handoff, and protected-context preservation. No automatic timeout fallback or globally ordered revision inference is allowed.

Check the agreed A/B scenario: A's context protects A's subsequent local read; B without transferred context may read 41 or `null` while 42 is propagating. Do not flag that accepted stale read as a RYOW defect or describe it as strict geographic consistency. B with transferred context must satisfy the carried requirement or fail explicitly.

For independent mode, review durable capture before acknowledgment, duplicate/reordered fan-out, original expiry, hint selection, backlog retention/backpressure, and gap-free catch-up. Optional all-target success must verify every captured target; never claim it creates strict consistency. Active-Active must not duplicate non-idempotent business mutations across instances. See backends.md.

## Severity

Critical: credential exposure, forged context crossing caller boundaries, or bypass of a separately required authorization policy. Important: a reproducible RYOW violation, unbounded wait, unsafe retry, context rollback, or false durability claim. Minor: clarity and maintainability without a behavioral impact.

Include trigger, consequence, requirement ID, and evidence for substantive findings. Keep minor findings to three. Distinguish an acknowledged RYOW limitation from a defect; stronger guarantees need a separate design decision. Reviewer findings do not manufacture approval or evidence that checks ran.
