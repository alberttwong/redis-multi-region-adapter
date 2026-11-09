# Review guidance

Use [spec.md](spec.md) as the behavior contract, [plan.md](plan.md) for scope, and [validation.md](validation.md) for proof. Review the configured backend, acknowledgment, recovery, and read policies together.

## Review passes

1. **Read correctness:** validate context, candidate/successor proof, exact lookup, bounded waiting, and outcome classification. Default latest must recheck candidates while waiting; exact reads never substitute a successor. No stale success, implicit downgrade, or missing-context bypass.
2. **Write lifecycle:** inspect latest-version construction, single-lineage sequencing, response reordering, idempotent retries, partial outcomes, and identity/content collisions. A next write is not a retroactive acknowledgment of an uncertain prior write.
3. **Distribution and recovery:** Active-Active writes once. Independent fan-out copies the same immutable envelope, not a repeated business mutation. Request-only refreshes on the next same-session insert/update. Enabled durable replay requires recoverable capture, expiry-safe delivery, no loops, retention, backpressure, and catch-up. All-target success verifies every captured member without timeout-driven shrinkage.
4. **Security and operations:** verify token/caller binding, authorized cross-device transfer, generation/expiry handling, exact backend compatibility, three primary shards per database, pooling, restore, and sanitized telemetry. Require integration evidence for each supported backend/recovery combination; request-only does not require a worker.

The agreed scenario permits B without A's context to read 41/null while A's 42 is unpropagated. That is not a RYOW defect. Neither a local hint, fan-out barrier, nor snapshot hit proves global latest state or current revocation. Describe an absent expected snapshot as **snapshot missing**, not as an infrastructure failure.

## Findings

Critical findings expose secrets, cross caller/security boundaries, or bypass a separately required authorization policy. Important findings violate a reproducible read/write/distribution contract, permit context rollback, create unbounded waits, or make false durability claims. Minor findings concern clarity or maintainability without a behavior impact.

For each substantive finding, give its trigger, consequence, requirement ID, and evidence. Limit minor findings to three. Review findings do not constitute approval, and unconfigured protections must not be described as enforced.
