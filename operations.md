# Operating the session adapter

Status: proposed operational requirements; no commands, workers, or automation implemented. Use [backends.md](backends.md) for transport mechanics and [validation.md](validation.md) for evidence.

## Record deployment and policy

For each region, record endpoint, geographic group, Redis Software build, database compatibility version, three primary data shards, replicas, persistence, capacity, eviction, and selected distribution mode. Record Active-Active identity when applicable; independent mode also records acknowledgment, recovery, target set, and configuration epoch. Verify supported commands for each actual backend. Keep credentials outside Git.

Cells and Redis targets change independently. Endpoint refresh must preserve caller context, snapshot/operation IDs, deadlines, and the selected policies. No implicit target removal, recovery change, or read-policy downgrade is permitted.

## Handle a missing snapshot

Validate context and inspect locally available state. Default `latest` rechecks both eligible successor candidates and the required exact snapshot during its bounded wait; explicit `required` checks only the exact identity. At deadline, an expected unexpired snapshot still unavailable is **snapshot missing** (`FreshnessUnavailable`, reason `snapshot_missing`). Ordinary unprotected absence may return null; explicit expiry, connectivity, authentication, integrity, and context errors remain distinct.

No remote fetch or old-value fallback occurs automatically. A newer default-read result needs verified history evidence; its numeric label alone is insufficient. Keep genuine first reads without context separate from missing expected context.

## Independent distribution

Request-only mode sends the new complete snapshot again on the next insert/update for the same session. It does not retain historical delivery obligations or require manual repair as the normal flow. If 43 arrives while exact 42 never does, default latest may use proven successor 43; exact 42 reports missing. Without another write, a remote region can remain stale.

When durable replay is enabled, monitor worker health, per-target backlog, oldest undelivered work, delivery conflicts, expiry, retries, and backpressure. Rehearse atomic-capture failure, request crash, worker restart, duplicate/reordered delivery, and gap-free new-target catch-up. Do not trim work before its retention/delivery contract permits it.

All-target timeout is a partial/uncertain result, not rollback. Reconcile the original snapshot/operation and captured target set. A later write does not turn an older uncertain result into success. Enabled replay may complete its copies independently of later requests.

## Expiry, restore, and region changes

Keep origin snapshots for the accepted context and retry horizons plus a safety margin. Destination retention applies to delivered copies; it does not promise delivery of missing historical snapshots in request-only mode. Bind server-assigned absolute expiry into context and records, with an agreed skew policy. Never reset TTL during replay or interpret an early miss as normal expiry.

After restore, eviction, or data regression, validate endpoint readiness and record integrity before restoring protected traffic. Recover retained work where available; missing records remain missing. Active-Active follows supported product catch-up procedures. Independent replay uses baseline plus gap-free replay; request-only targets receive future writes and do not claim historical catch-up. Configuration changes preserve outstanding all-target obligations.

## Observe and release

Measure ordinary misses, snapshot-missing outcomes, freshness waits, candidate rejection, context/proof errors, infrastructure failures, partial writes, fan-out success per target, replay backlog when enabled, pool saturation, and shard skew. Use opaque correlation IDs; exclude payloads, bearer IDs, credentials, and raw tokens. Agree numeric targets and paging ownership before launch.

Rehearse each supported combination in staging, then limit initial traffic. Rollback preserves envelope/token compatibility, sequencing, expiry, and the chosen contract. Pause protected operations if an older version cannot honor it. No release gate or permission control is installed by these documents.

An incident record captures the violated requirement, sanitized evidence, policy/topology, mitigation, and uncertainty. Add a regression scenario and propose follow-up intent. Current authorization/revocation remains a separate service/security responsibility.
