# Multi-region session consistency

Documentation-only repository. Start with README.md, then spec.md and plan.md. No application build, test, lint, or deployment commands exist. Add verified commands after the implementation stack is selected.

## Required behavior

- Target Redis Software 8.x, three primary shards per regional database; replicas additional. Support Active-Active and independent fan-out modes.
- Separate convergence, read behavior / consistency (Available/Session/linearizable; Session provides RYOW, not full causal consistency), and linearizable cluster-group scope (geographic/global). Group membership alone enforces no guarantee; linearizable reads are deferred. RYOW follows the caller across groups; explicit `available` has no freshness guarantee.
- Default read is `session`. Carry authenticated caller context. A local successor needs verified lineage/history evidence; a higher number alone is insufficient.
- Recheck both the local candidate and required snapshot while waiting on a default read. Exact lookup is internal plumbing; there is no public `required` or raw-record read. Explicit `available` permits older valid local state or null.
- Describe an absent expected snapshot as **snapshot missing**; keep infrastructure, integrity, context, and expiry outcomes distinct.
- A1/A2 read/write us-west-2; B1 reads/writes us-east-1; C1 reads/writes us-east-2; D1 reads/writes eu-west-1; E1 reads/writes eu-central-1. US groups the three US regions; EU groups the two EU regions. Each keeps its own context with no cross-client sharing. A1/A2 share a regional database in the example, but not a lineage. Local discovery avoids WAN delay only where the candidate is actually published. Defaults do not change. Groups do not automatically change the captured all-target acknowledgment set.
- Independent request-only mode refreshes through the next insert/update's latest version, not mandatory manual repair or historical replay. Durable replay is optional; capture its obligation before success when enabled.
- Local acknowledgment is the baseline. Optional independent all-target acknowledgment verifies placement, not strict ordering. Never silently drop a target on timeout.
- Serialize writes per caller lineage; prevent response/context rollback. No fixed home cluster, automatic remote read fallback, or linearizable geographic/global guarantee.
- Never log session payloads, raw context, bearer IDs, or credentials.

## Completion evidence

Use validation.md and REVIEW.md. Keep spec.md and plan.md synchronized with implementation. Proposed scenario descriptions are not test results. Report actual checks and unresolved design decisions; documents do not install controls or provision infrastructure.
