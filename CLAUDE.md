# Multi-region session consistency

## Context

Documentation-only repository. Read README.md, intent.md, spec.md, and plan.md. The selected target is read-your-own-writes (RYOW), using Redis Software 8.x with three primary data shards per regional database; replicas are additional. Pin exact builds before deployment.

## Commands

No build, test, lint, provisioning, or deployment commands exist. Add verified commands and expected outcomes after selecting the implementation stack. Do not claim proposed tests have run.

Read backends.md for Active-Active and independent regional modes. Independent mode needs adapter-managed fan-out and an explicit request-only or durable-replay recovery policy; local polling alone does not replicate. Active-Active writes once. Optional all-target acknowledgment verifies placement, not strict ordering.

## Rules

- RYOW is selected; L1/L2/S1 are historical alternatives, not open strategy choices for this phase.
- Bind an immutable snapshot to authenticated caller context. Middleware must propagate context across region changes.
- A protected read returns its required unexpired snapshot, a proven descendant for `latest`, or a freshness/infrastructure error. Never return older state or a propagation miss as successful `null`.
- Default reads to `latest`: local candidate constrained by caller RYOW context. Return a newer candidate only with verified lineage/incorporation evidence; otherwise retrieve/wait for the required snapshot or error. Without prior context this is eventual discovery.
- Device B may explicitly select `required` (exact version via authorized context handoff) or `any` (local candidate, older/newer allowed, absent returns `null`). Never downgrade automatically or let any-version reads replace protected context.
- An unprotected exact-ID miss may return `null`; distinguish explicit expiry from unavailable data.
- Local discovery hints serve `any` and default `latest`. They are eventual; only additional caller-context validation can establish RYOW. Never treat them as global latest-state or authorization proof.
- Serialize writes in one caller lineage; prevent older responses from replacing newer context.
- No automatic remote fallback, strict commit authority, or fixed home cluster. Default acknowledgment does not wait for all regions; independent mode can explicitly select all-target placement acknowledgment.
- Agreed A/B behavior: after A writes 42, A reads 42/proven successor with context; B without transferred context may read local 41 or `null`. B with context must satisfy it or fail.
- RYOW does not guarantee another caller's newest update or immediate global revocation.
- Three shards do not constitute regions or consensus. Cells and Redis membership are distinct.
- Exclude session payloads, bearer IDs, credentials, and raw context from logs.

## Evidence

Use validation.md and REVIEW.md; keep the specification and plan current. Report actual checks and unresolved limitations. Documents do not install hooks or deploy infrastructure.
