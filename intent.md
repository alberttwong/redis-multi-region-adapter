# Intent: multi-region read behavior

Date: 2026-11-09. Status: default and read behaviors selected; implementation proposed.

## Outcome

Provide two production reads over regional copies: **Local** (`local`) queries one local cluster; **Available** (`available`, default) concurrently queries every cluster in the selected group, including local, and returns the first valid non-null value. If all replies are null, or no value arrives before the shared deadline, Available returns null. An early null must not end the race while other members are pending.

Available chooses a value by arrival time, not freshness. Either option may return stale data or miss a completed write; neither guarantees read-your-own-writes. Timeout-null is not proof that every cluster lacks the value. Keep authorization, integrity, expiry, deadlines, and per-attempt observability intact.

Session and Causal read options have been removed. Proposed **Monotonic** (`monotonic: true`, default off) is an optional guarantee on Local/Available that asks whether a caller can read without going backward from its last tracked successful observation. It keeps Local local-only and Available group-scoped while automatically retaining/transporting read history and rejecting older or unproven state on either backend. It provides last-observed freshness once the floor is established, while it may still miss newer writes. This is non-regression, not a maximum staleness age, real-time freshness, or RYOW. The integration is unimplemented and requires state-history proofs, safe floor updates, and bounded wait/failure handling.

**Linearizable over Active-Active** and **Linearizable over Coordinated** target the same real-time ordering/freshness per key through different replication backends and custom coordination. No such protocol is implemented. Both implementations have **slow++** read/write planning ratings; these are qualitative estimates, not measured guarantees. Native Active-Active causal consistency remains optional backend configuration, not a read behavior or a substitute for Monotonic/Linearizable enforcement.

## Topology and scope

A1/A2 share a regional database in `us-west-2`; B1 uses `us-east-1`, C1 `us-east-2`, D1 `eu-west-1`, and E1 `eu-central-1`. US groups the three US regions and EU the two EU regions. Five regional databases with three primary shards each mean fifteen primaries before replicas. Confirm actual cell/endpoint placement.

Available selects the local region's configured read group, or a validated explicit override, always including local. A configured global group can include all five. Local never fans out. Clients do not exchange application context; database transport carries data between regions. Group membership defines Available's read targets without enforcing ordering or changing write acknowledgment participants.

## Distribution choices

**Both Active-Active and independent regional clusters are supported.** Consider Active-Active when its additional native CRDT conflict resolution, replication catch-up, and optional same-key causal ordering are useful. Independent clusters use adapter-managed distribution, a reduced subset of those capabilities, and remain a supported choice when that behavior meets application requirements. Choose based on required capabilities, operational responsibilities, and total cost. The adapter's Local/Available read contract can be layered over either backend.

Support Redis Software 8.x Active-Active or independent regional clusters with adapter fan-out. Active-Active owns replication recovery; independent mode uses bounded request-time fan-out with no background repair. Each later same-session write distributes its current value; without another write, missed delivery may stay unrepaired indefinitely. No separate recovery selector or durable replay option is planned. Local acknowledgment is baseline; independent `all-targets` verifies the captured full target set.

A1 writing 42 does not make either read behavior wait for 42. Local reads the regional candidate; Available can obtain a value from any group member, including local, and an older first value can win. All-target write placement does not create linearizability. See [consistency.md](consistency.md), [backends.md](backends.md), and [spec.md](spec.md).

## Prefer native Redis Enterprise capabilities

Build the adapter on top of, or make it work with, the [official Redis clients](https://redis.io/docs/latest/develop/clients/), initially **Jedis for Java** and **redis-py for Python**. Preserve the same read/write contract across supported client integrations and reuse their existing facilities.

Use Redis Enterprise native data/conflict semantics, persistence/durability, expiration, capacity/eviction, and existing client pooling/timeouts. Treat version/client selection, supported commands, configured groups, and limits as integration configuration, not new product features. Build only the selected baseline adapter behavior and necessary validation/cleanup. Automatic monotonic history and linearizable coordination remain deferred extensions requiring additional code; they are not supplied by the native baseline.

## Delivery and limits

Build the proposed public API, validate bounded fan-out/cancellation/error semantics, and measure outcomes with the scenarios in [validation.md](validation.md). The [AWS spike](spike/README.md) retains historical controls/results; it does not implement the revised group-racing Available policy. No production SDK, linearizable protocol, or immediate cross-device revocation guarantee is established. Keep retained data, credentials, payloads, and bearer IDs out of logs and PR artifacts.
