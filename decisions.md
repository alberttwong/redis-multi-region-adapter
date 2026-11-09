# Deployment and write-policy decisions

Status: design options; no implementation. Read policy remains **latest-local-ryow** by default, with explicit exact-version and any-version reads. Redis Software 8.x uses three primary data shards per regional database, plus replicas.

## Decision flow

```mermaid
flowchart TD
    Start[Choose regional distribution] --> AA{Use Active-Active?}
    AA -->|Yes| Native[Write once at origin; Redis distributes]
    Native --> Reads[Apply latest-local-ryow read policy]
    AA -->|No| Fanout[Adapter sends same immutable snapshot to all configured regions]
    Fanout --> Recovery{Persist unfinished delivery work?}
    Recovery -->|Yes| Durable[Durable replay: capture recoverable obligation and retry after restart]
    Recovery -->|No| Request[Request-only: attempt fan-out again on the next insert or update]
    Durable --> Ack{When may write return success?}
    Request --> Ack
    Ack -->|Origin accepted| Local[Local acknowledgment; remote copies may be missing]
    Ack -->|Every target verified| All[All-target acknowledgment; partial failure prevents success]
    Local --> Reads
    All --> Reads
```

Distribution, recovery, and acknowledgment are independent choices. Active-Active's managed replication is not the same as enabling the application's durable outbox. In independent mode, select recovery explicitly; durable replay is optional, not a mandatory or implicitly selected feature. Local acknowledgment remains the baseline; all-target verification is opt-in.

## Write acknowledgment and crash recovery

The four independent-backend combinations share the same immutable fan-out operation. Acknowledgment and recovery are separate settings.

```mermaid
flowchart TD
    Fanout["Independent regional fan-out"] --> Local{"Acknowledge after origin acceptance?"}
    Local -->|Yes| LocalReplay{"Durable replay enabled?"}
    LocalReplay -->|No| B["B: Local + request-only"]
    LocalReplay -->|Yes| C["C: Local + durable replay"]
    B --> BResult["Local success allowed; next insert or update sends its snapshot to all regions"]
    C --> CResult["Local success only after recoverable obligation; worker resumes after crash"]
    Local -->|No: all targets| AllReplay{"Durable replay enabled?"}
    AllReplay -->|No| D["D: All-targets + request-only"]
    AllReplay -->|Yes| E["E: All-targets + durable replay"]
    D --> DResult["Success only after every target verifies; next insert or update attempts fan-out again"]
    E --> EResult["Same success barrier; worker can finish saved copies after failure or crash"]
```

Option A is Active-Active: write once at the origin and let Redis manage transport and recovery under the configured persistence/availability contract. It does not require an application outbox for regional transport.

B and D attempt distribution again on the next insert/update for the same session. Each write carries a complete immutable snapshot, so a successful later delivery can refresh current local state without replaying every historical snapshot. With no later write, a region can remain stale. Request-only mode does not retain a crash-surviving historical delivery obligation. A successful all-target write proves placement at acknowledgment under its contract, not permanent availability, rollback of partial copies, or strict geographic consistency.

## Version 42 when Region B is unavailable

```mermaid
flowchart TD
    Write["Origin A accepts snapshot 42; Region B is unavailable"] --> Policy{"Acknowledgment policy?"}
    Policy -->|Local| Saved{"Durable replay enabled?"}
    Saved -->|No| Local["Write may succeed locally; next insert or update attempts delivery again"]
    Saved -->|Yes| Capture["Write succeeds only after recoverable obligation is accepted"]
    Capture --> Worker["Worker retries B within retention and durability contract"]
    Policy -->|All targets| Deadline["Cannot return all-target success while B is missing"]
    Deadline --> Unknown["At deadline return partial or uncertain outcome; preserve IDs and target set"]
    Unknown --> Repair{"Durable replay enabled?"}
    Repair -->|Yes| Worker
    Repair -->|No| NextWrite["Next same-session insert or update fans out its new snapshot"]
    Local --> Read["B with context returns 42 or proven successor; otherwise snapshot missing at deadline"]
    Worker --> Read
    NextWrite --> Read
```

Active-Active has the local-acknowledgment behavior with Redis-owned transport rather than the application's replay worker. Without context for 42, B's default latest-local read may return 41 or null while delivery is incomplete. No option automatically transfers A's context to B.

An uncertain write does not issue normal successful-write context. Authenticated recovery/handoff may identify its pending immutable snapshot while preserving the uncertain status until reconciled. Partial errors do not mean existing copies were rolled back.

## Read-policy flow

Authorization, context integrity, generation, and expiry checks apply before successful returns. Invalid or lost expected context is an error, distinct from a genuine first read.

```mermaid
flowchart TD
    Read["Read at selected regional endpoint"] --> Policy{"Read policy?"}
    Policy -->|latest: default| Context{"Prior-write context?"}
    Context -->|No| Candidate["Read valid local candidate; return candidate or null"]
    Context -->|Yes| Match{"Local candidate proves it follows required write?"}
    Match -->|Yes| Return["Return eligible candidate; advance context safely"]
    Match -->|No| LatestWait["Recheck candidate and exact required snapshot within deadline"]
    LatestWait --> LatestResult["Return required snapshot or proven successor; otherwise snapshot missing"]
    Policy -->|required: exact version| Exact["Look up only the requested immutable snapshot"]
    Exact --> Present{"Valid exact snapshot present?"}
    Present -->|Yes| Snapshot["Return exact snapshot without lowering protected context"]
    Present -->|No| ExactWait["Wait for exact identity; report snapshot missing at deadline"]
    Policy -->|any: explicit opt-in| Candidate
```

`required` needs authenticated exact-version context; `any` never replaces protected caller context. Infrastructure, integrity, and context failures remain distinct errors rather than null or snapshot-missing results. An explicitly expired record has the separately defined expired outcome. No flow automatically falls back to an older value after freshness failure.

Do not automatically switch reads or acknowledgment policy after a timeout. Keep operation ID, snapshot ID, target set, and selected policies in sanitized recovery evidence. Neither fan-out nor replay supplies shared strict commit ordering.

A next write of 43 can make B's current state available without filling every historical gap. If exact 42 is absent, report **snapshot missing**. Default latest with context 42 may return 43 only when it is a proven successor; otherwise its required snapshot remains missing. An unrelated session write does not refresh this session. An uncertain all-target write keeps its original outcome; a later successful update does not retroactively acknowledge it.

For protocol obligations and open implementation choices, see [backends.md](backends.md), [spec.md](spec.md), and [validation.md](validation.md).
