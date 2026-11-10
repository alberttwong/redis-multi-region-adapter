# Review guidance

Use [spec.md](spec.md) as the contract, [plan.md](plan.md) for implementation scope, and [validation.md](validation.md) for evidence. Production APIs are proposed; legacy spike behavior is distinct.

## Review passes

1. **Available race:** every captured group member, including local, starts concurrently. Return first valid non-null value immediately; a null reply does not stop pending attempts. Return null only on all-null completion or the shared deadline without a value. No newest-value comparison, quorum, repair, or sequential fallback.
2. **Local and errors:** Local contacts one regional endpoint. Validate authorization, binding, integrity, generation, and expiry for both reads. Preserve Local infrastructure errors and request-level configuration/access errors; Available per-target failures do not cancel healthy attempts. Distinguish deadline-null from confirmed all-null in telemetry.
3. **Resource lifecycle:** shared bounded deadline, bounded group fan-out/pools, cancellation, and disposal of loser/late replies. A winner must not await slow cleanup. Group membership is fixed per operation and includes local; unauthorized or malformed overrides fail before dispatch.
4. **Write/distribution:** stable IDs, immutable envelopes, no repeated business mutations on fan-out, original expiry, uncertain-write reconciliation, request-only next-write refresh, and optional durable replay capture/recovery. All-target success verifies the entire captured target set and does not establish linearizability.
5. **Causal configuration:** verify native Active-Active causal consistency is enabled for the relevant operations. Preserve same-key causal dependencies without claiming cross-key order, cross-region catch-up, or linearizability. Native ordering reduces custom code, but deployment/adapter validation remains necessary.
6. **Stronger options:** Linearizable requires Active-Active as a project rule plus a separate validated coordination protocol. Coordinated targets independent clusters; do not infer linearizability or freshness from its name. Require a precise contract for ordering, commit/read safety, fencing/failover, and deadline/partition behavior before enablement. Both remain unsupported; reject rather than downgrade.
7. **Scope and evidence:** no production Session option, caller write-context automation, or public exact-version selector. Read groups do not shrink write obligations. Active-Active provides eventual convergence. Historical spike tests/results are not production acceptance for group-racing Available.

## Severity and completion

Critical findings expose secrets, cross caller/security boundaries, or bypass authorization. Important findings violate the documented race, return early null, accept invalid state, leak unbounded work, or make false ordering/durability claims. Minor findings concern clarity or maintainability without behavioral impact. Confirm the five-region/six-client sizing and review actual measurements/tests rather than proposed scenarios alone.
