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
    Recovery -->|No| Request[Request-only: bounded attempts; caller or operator owns later repair]
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
    B --> BResult["Local success allowed; failed remote copies need caller or operator repair"]
    C --> CResult["Local success only after recoverable obligation; worker resumes after crash"]
    Local -->|No: all targets| AllReplay{"Durable replay enabled?"}
    AllReplay -->|No| D["D: All-targets + request-only"]
    AllReplay -->|Yes| E["E: All-targets + durable replay"]
    D --> DResult["Success only after every target verifies; partial failure needs caller reconciliation"]
    E --> EResult["Same success barrier; worker can finish saved copies after failure or crash"]
```

Option A is Active-Active: write once at the origin and let Redis manage transport and recovery under the configured persistence/availability contract. It does not require an application outbox for regional transport.

B and D do not promise eventual regional convergence after a failed copy or process crash. Request-local retries do not survive process loss. A successful all-target write proves placement at acknowledgment under its contract, not permanent availability, rollback of partial copies, or strict geographic consistency.

## Version 42 when Region B is unavailable

```mermaid
flowchart TD
    Write["Origin A accepts snapshot 42; Region B is unavailable"] --> Policy{"Acknowledgment policy?"}
    Policy -->|Local| Saved{"Durable replay enabled?"}
    Saved -->|No| Local["Write may succeed locally; missing B copy needs external repair"]
    Saved -->|Yes| Capture["Write succeeds only after recoverable obligation is accepted"]
    Capture --> Worker["Worker retries B within retention and durability contract"]
    Policy -->|All targets| Deadline["Cannot return all-target success while B is missing"]
    Deadline --> Unknown["At deadline return partial or uncertain outcome; preserve IDs and target set"]
    Unknown --> Repair{"Durable replay enabled?"}
    Repair -->|Yes| Worker
    Repair -->|No| Caller["Caller or operator reconciles the same snapshot"]
    Local --> Read["B with authenticated context waits for 42 or returns freshness error"]
    Worker --> Read
    Caller --> Read
```

Active-Active has the local-acknowledgment behavior with Redis-owned transport rather than the application's replay worker. Without context for 42, B's default latest-local read may return 41 or null while delivery is incomplete. No option automatically transfers A's context to B.

An uncertain write does not issue normal successful-write context. Authenticated recovery/handoff may identify its pending immutable snapshot while preserving the uncertain status until reconciled. Partial errors do not mean existing copies were rolled back.

## Read-policy flow

Authorization, context integrity, generation, and expiry checks apply before successful returns. Invalid or lost expected context is an error, distinct from a genuine first read.

```mermaid
flowchart TD
    Read["Read at selected regional endpoint"] --> Policy{"Read policy?"}
    Policy -->|latest: default| Context{"Prior-write context?"}
    Context -->|No| Candidate["Read local valid candidate; return candidate or null"]
    Context -->|Yes| Match{"Local candidate proves required write is included?"}
    Match -->|Yes| Return["Return eligible candidate; advance context safely"]
    Match -->|No| Exact["Look up required immutable snapshot"]
    Policy -->|required: exact version| Exact
    Exact --> Present{"Valid exact snapshot present?"}
    Present -->|Yes| Snapshot["Return exact requested snapshot"]
    Present -->|No| Wait["Bounded local wait; return snapshot on arrival or freshness error at deadline"]
    Policy -->|any: explicit opt-in| Candidate
```

`required` needs authenticated exact-version context; `any` never replaces protected caller context. Infrastructure and integrity failures remain errors rather than null results. An explicitly expired record has the separately defined expired outcome. No flow automatically falls back to an older value after freshness failure.

Do not automatically switch reads or acknowledgment policy after a timeout. Keep operation ID, snapshot ID, target set, and selected policies in sanitized recovery evidence. Neither fan-out nor replay supplies shared strict commit ordering.

For protocol obligations and open implementation choices, see [backends.md](backends.md), [spec.md](spec.md), and [validation.md](validation.md).
