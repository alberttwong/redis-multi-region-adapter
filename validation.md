# Validation: read-your-own-writes

Status: proposed acceptance scenarios; no implementation or execution results

Traceability: R identifiers refer to [spec.md](spec.md).

| Case | Requirements | Stimulus and expected observation |
| --- | --- | --- |
| V01 | R01 | Read back each regional deployment: Redis Software 8.x build/compatibility version, selected mode verified (Active-Active enabled, or independent databases with configured replay workers), three primary data shards, replicas separate. |
| V02 | R02 | Round-trip envelopes and context. Detect conflicting record identity, digest corruption, generation mismatch, schema mismatch, and attempted payload overwrite. |
| V03 | R03, R04 | Acknowledge a write in A, carry its context, then read in B. Exercise same-cell if deployed, same-region, cross-region, and US/EU movement. Return the exact required snapshot. |
| V04 | R05, R09 | Compare unprotected miss (`null`), protected unexpired miss (bounded wait then freshness error), explicit expiry, connection rejection, TLS/authentication failure, and timeout. Do not conflate them. |
| V05 | R04, R05 | Leave old session state at B; delay the required snapshot. Never return the older payload. If the snapshot arrives within deadline, return it; otherwise return freshness error. |
| V06 | R02, R06 | Lose the write response; retry same IDs against the origin. Reconcile the same envelope/context without a new logical mutation. Unreachable origin remains uncertain. Conflicting payload reuse surfaces an error. |
| V07 | R05 | Partition destination from origin after local write success. Write does not wait for all regions; protected destination read never succeeds with stale state. Waiting and connection use are bounded. |
| V08 | R03, R08 | Omit, forge, truncate, replay across sessions, or use unsupported context. Protected operation rejects rather than silently switching to eventual semantics. Verify middleware forwards context on every protected request. |
| V09 | R07 | Reorder responses and attempt two in-flight writes in one lineage. Enforce serialization and prevent older context replacing newer context. Dependent reads carry the last acknowledged context. |
| V10 | R09, R11 | Expire a snapshot/context under controlled clocks; verify explicit expired outcome. Delete data before expiry: freshness failure rather than expiration. Test agreed skew margin. |
| V11 | R10 | Replace cells and regional endpoints during traffic. Preserve context, operation IDs, deadlines, and protected-read semantics without assigning a fixed home cluster. |
| V12 | R10, R11 | Evict, restart, restore, or join an instance missing the required record. A healthy connection never substitutes for matching data. Recover or fail explicitly; validate retained snapshots throughout promised lifetime. |
| V13 | R12 | Bound poll rate, retries, request sizes, pool use, and cancellation. Inspect telemetry for payloads, raw context, credentials, and bearer IDs. |
| V14 | R13 | Another caller creates newer state or revokes access. Demonstrate that RYOW may still return this caller's valid required snapshot. Document the limitation and exercise any separately required authorization check. |
| V15 | R12 | Load representative session sizes and caller concurrency across three shards. Measure p50/p95/p99 write/read latency, freshness wait/failure rate, replication lag, shard skew, and throughput against agreed targets. |
| V16 | R14 | Store 41 in B while 42 is delayed. Required 42 waits/errors; explicit any returns local 41. When 42 or 43 becomes the local candidate, any may return it. Assert actual version/policy metadata and no implicit downgrade. |
| V17 | R14 | Remove or expire B's any-version hint while snapshots remain; any returns `null`. Hint corruption/connectivity failure remains an error. Regress the hint: any may return older valid state but never rolls protected context back or bypasses generation/security rules. |
| V18 | R15 | A writes 42; authenticated handoff issues context for authorized B. B's required read returns exactly 42 or freshness error. Reject wrong-device/session tokens and missing context. A present 43 never substitutes for exact 42. |
| V19 | R04, R14 | Omit read policy and verify `latest`. Context 42 plus local proven descendant 43 returns 43 and advances context. Local 41, absent candidate, or incomparable 43 falls back to exact 42 or bounded freshness failure. First read without prior context uses eventual local discovery. Lost expected context and invalid proof never silently weaken RYOW. Explicit exact 42 still returns 42 when 43 exists. |
| V20 | R16 | Complete A's write 42, then read A locally with context and B locally without it while replication is delayed. A returns 42/proven successor; B may return local 41 or `null`. Transfer context to B: its default read now waits for 42/proven successor or fails explicitly. After catch-up, B can return 42. Verify no automatic context inheritance and record that stale B success would violate the deferred strict geographic contract within the same group. |
| V21 | R17 | In independent mode, crash after capture, lose responses, and duplicate/reorder deliveries. Restart the worker: every retained obligation completes idempotently with matching IDs/digests, original expiry, no replay loops, no same-lineage hint rollback, bounded backlog/backpressure, and gap-free new-target catch-up. Missing durable capture prevents successful acknowledgment. |
| V22 | R18 | Compare local-durable-replay with all-targets while delaying or partitioning B. Default local success allows B lag; all-targets success waits for every captured target to verify. Deadline yields partial/uncertain outcome with unchanged target set; retries reconcile. Confirm this does not claim atomic visibility, global ordering, or disk durability from readback. |

## Evidence

Use unit tests for context/envelope/configuration behavior, middleware contract tests for caller ordering, and real Redis Software integration tests for both Active-Active and independent/replay configurations to exercise region movement and replication. A single-node test cannot certify this guarantee. Capture sanitized invocation/response histories, origin and destination, build, persistence, primary/replica layout, context sequence (not raw token), fault schedule, and results.

The oracle checks caller-local RYOW, not global latest-state linearizability. For each protected read beginning after an acknowledged write and carrying its context, assert the returned snapshot matches the required identity, or for default latest-local is proven to incorporate it, or a typed failure is explicit. Failure is acceptable for safety during a partition; agreed service levels separately govern availability.

## Agent configuration checks

Replay tasks involving stale hits, lost context, response reordering, expiry versus missing data, unsupported Redis capabilities, and accidental strict-consistency claims when instructions change. No eval runner or enforcement hooks are installed. This Markdown change has only documentation checks, not application test results.
