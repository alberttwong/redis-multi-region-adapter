# Intent: multi-region read behavior

Date: 2026-11-09. Status: default and read behaviors selected; implementation proposed.

## Outcome

Provide two production reads over regional copies: **Local** (`local`) queries one local cluster; **Available** (`available`, default) concurrently queries every cluster in the selected group, including local, and returns the first valid non-null value. If all replies are null, or no value arrives before the shared deadline, Available returns null. An early null must not end the race while other members are pending.

Available chooses a value by arrival time, not freshness. Either option may return stale data or miss a completed write; neither guarantees read-your-own-writes. Timeout-null is not proof that every cluster lacks the value. Keep authorization, integrity, expiry, deadlines, and per-attempt observability intact.

The Session read option and its automatic context/lineage implementation have been removed from the production scope. Exact versions remain internal write/distribution metadata, not caller-selectable reads. Linearizable behavior is deferred and requires a separately validated coordination protocol; Active-Active alone supplies eventual convergence.

## Topology and scope

A1/A2 share a regional database in `us-west-2`; B1 uses `us-east-1`, C1 `us-east-2`, D1 `eu-west-1`, and E1 `eu-central-1`. US groups the three US regions and EU the two EU regions. Five regional databases with three primary shards each mean fifteen primaries before replicas. Confirm actual cell/endpoint placement.

Available selects the local region's configured read group, or a validated explicit override, always including local. A configured global group can include all five. Local never fans out. Clients do not exchange application context; database transport carries data between regions. Group membership defines Available's read targets without enforcing ordering or changing write acknowledgment participants.

## Distribution choices

Support Redis Software 8.x Active-Active or independent regional clusters with adapter fan-out. Active-Active owns replication/recovery; independent mode requires it in the application. Local acknowledgment is baseline; independent `all-targets` explicitly verifies the captured full target set. Independent recovery is separately chosen as request-only next-write refresh or optional durable replay. Without another write or retained replay obligation, an idle target may remain stale.

A1 writing 42 does not make either read behavior wait for 42. Local reads the regional candidate; Available can obtain a value from any group member, including local, and an older first value can win. All-target write placement does not create linearizability. See [consistency.md](consistency.md), [backends.md](backends.md), and [spec.md](spec.md).

## Delivery and limits

Build the proposed public API, validate bounded fan-out/cancellation/error semantics, and measure outcomes with the scenarios in [validation.md](validation.md). The [AWS spike](spike/README.md) retains historical controls/results; it does not implement the revised group-racing Available policy. No production SDK, linearizable protocol, or immediate cross-device revocation guarantee is established. Keep retained data, credentials, payloads, and bearer IDs out of logs and PR artifacts.
