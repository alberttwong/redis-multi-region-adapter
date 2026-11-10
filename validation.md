# Validation: Local and Available reads

Status: proposed production acceptance scenarios, not executed results. Requirements refer to [spec.md](spec.md). Legacy spike tests/results exercise different controls and do not certify group-racing Available.

| Case | Requirements | Stimulus and expected observation |
| --- | --- | --- |
| V01 | R01 | Verify exact platform/client/build/commands, Active-Active or independent mode, three primaries per regional database plus replicas, five databases and six clients. |
| V02 | R02, R08 | Round-trip immutable envelopes; reject identity/content collisions, wrong key/session binding, generation violations, digest corruption, and invalid expiry. Preserve original expiry when copying. |
| V03 | R03 | Omit policy with default configuration: Available dispatches all selected group members including local. Explicit Local contacts only its one regional endpoint. |
| V04 | R03 | Put a value only in a remote member. Local returns null while Available obtains the remote value. No caller version/context input is needed. |
| V05 | R04, R05 | Block every member behind an observed dispatch barrier. Verify every distinct group request starts concurrently including local; release local with a valid value and verify immediate return without awaiting remote replies. |
| V06 | R04, R06 | Local replies null first, remote member later returns a value before deadline: return that value. Repeat with several early nulls; no early null may end the race. |
| V07 | R05, R14 | Return stale 41 before newer 42: 41 wins. Later values cannot replace it. Neither completed own writes nor numeric versions force freshness or agreement. |
| V08 | R06, R07 | All members return null at different times: return null after the final null, before deadline. With one member silent, return null only at deadline; discard a late value. |
| V09 | R06, R07, R09 | One member fails connection while another returns a value: return the value. With only nulls plus failed/silent members, return null at shared deadline. Distinguish all-null and deadline-null telemetry. Local connection/timeout failures remain errors. |
| V10 | R04, R10 | Exercise US (three), EU (two), explicit global (five), same-region A1/A2, and allowed overrides. Include local exactly once, exclude outside-group clusters, and capture membership/epoch before a concurrent topology change. |
| V11 | R03 | Reject unknown policies, removed Session/exact-version/Greedy controls, deferred linearizable, empty/unknown groups, local excluded, unresolved endpoints, and unauthorized overrides before dispatch. |
| V12 | R02, R12 | Lose write response and retry the same operation/record IDs. Reconcile identical effects; conflicting reuse errors. Do not repeat business mutation or claim rollback/retroactive success. |
| V13 | R07, R15 | Bound group fan-out, pools, retries, memory, and cancellation. A winner returns before loser cleanup. Repeated timeouts/late replies do not leak tasks/connections or mutate completed results. |
| V14 | R08, R09 | Request-level authorization/configuration errors remain errors. Invalid/expired candidates never win; an invalid member does not cancel another valid winner. Local corruption/connectivity is not a null success. Apply the specified Available no-value deadline semantics and record rejection reasons. |
| V15 | R10, R12 | US read group with all-five-target writes: missing either EU target prevents all-target success; US reads never shrink that write set. Local write acknowledgment does not wait for group/foreign delivery. |
| V16 | R11 | Request-only partial fan-out then process exit: no durable worker obligation is promised. Next same-session update sends its latest version to all targets; unrelated session writes do not refresh it. No further writes can leave stale regions indefinitely. |
| V17 | R11 | Enabled durable replay atomically captures accepted obligations; crash/restart/duplicates preserve IDs/digests/expiry and complete retained work without another write. Verify capacity/backpressure and no replay loop. |
| V18 | R13 | Restore/evict/join targets, change epochs, and expire records under controlled clocks. Respect backend readiness/catch-up and original expiry. Do not fabricate freshness or authorization from endpoint health. |
| V19 | R14 | Demonstrate Local/Available stale/null after a completed write, and that all-target placement does not establish linearizability. Keep current cross-device revocation checks separate. |
| V20 | R15 | Measure Local and Available per group/origin/winner/outcome at realistic payload/rate. Report end-to-end all-attempt/success-value p50/p95/p99 plus all-null/deadline-null/errors, per-member load, cancellations, and late work. Do not average p99s or infer new behavior from legacy runs. |

## Evidence

Add meaningful unit/contract tests for dispatch, races, validation, deadlines, cancellation, and policy resolution; integration/fault/load tests need real supported deployments. Capture sanitized invocation/response traces and fault schedules. No production implementation of the revised Available contract or executed acceptance suite is claimed here. Follow [latency.md](latency.md) for measurement and [REVIEW.md](REVIEW.md) for review priorities.
