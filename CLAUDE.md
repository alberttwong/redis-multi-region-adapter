# Multi-region session consistency

Documentation-only repository. Start with README.md, then spec.md and plan.md. No application build, test, lint, or deployment commands exist. Add verified commands after the implementation stack is selected.

## Required behavior

- Target Redis Software 8.x, three primary shards per regional database; replicas additional. Support Active-Active and independent fan-out modes.
- Default read is `latest-local-ryow`. Carry authenticated caller context. A local successor needs verified lineage/history evidence; a higher number alone is insufficient.
- Recheck both the local candidate and required snapshot while waiting on a default read. Explicit `required` returns only the exact requested snapshot. Explicit `any` permits older valid local state or null.
- Describe an absent expected snapshot as **snapshot missing**; keep infrastructure, integrity, context, and expiry outcomes distinct.
- A reads/writes in us-west-2; independent B reads/writes in us-east-1. Defaults are unchanged. Each uses context from its own writes; they do not communicate or share context/version IDs. A reads 42/proven successor using A’s own context. B may read local 41/null and cannot know unpropagated 42 exists. No cross-device handoff or shared version directory is in scope.
- Independent request-only mode refreshes through the next insert/update's latest version, not mandatory manual repair or historical replay. Durable replay is optional; capture its obligation before success when enabled.
- Local acknowledgment is the baseline. Optional independent all-target acknowledgment verifies placement, not strict ordering. Never silently drop a target on timeout.
- Serialize writes per caller lineage; prevent response/context rollback. No fixed home cluster, automatic remote read fallback, or strict geographic/global guarantee.
- Never log session payloads, raw context, bearer IDs, or credentials.

## Completion evidence

Use validation.md and REVIEW.md. Keep spec.md and plan.md synchronized with implementation. Proposed scenario descriptions are not test results. Report actual checks and unresolved design decisions; documents do not install controls or provision infrastructure.
