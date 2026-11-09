# Operations: read-your-own-writes

Status: proposed procedures; no automation implemented

Related: [spec.md](spec.md), [validation.md](validation.md)

## Deployment

Record each regional endpoint, geographic group, distribution mode, Active-Active identity when applicable, Redis Software 8.x build, compatibility version, three primary data shards, replicas, persistence, eviction policy, and capacity. Keep credentials outside Git. Confirm supported commands against the deployed Active-Active configuration.

Redis handles transport in Active-Active mode; independent mode requires the durable fan-out/replay path in [backends.md](backends.md). Default acknowledgment does not wait for every target; optional independent `all-targets` acknowledgment does. Cell changes update application endpoint discovery; Redis participant changes follow supported product procedures and readiness checks. Neither change may drop caller context.

## Freshness and recovery

On a protected read, validate context, check the selected endpoint for the exact snapshot, then retry within the configured budget. At deadline, return a typed freshness-unavailable error. Do not return older state, silently fetch remotely, or turn the error into a cache miss. Infrastructure errors remain distinct.

After restore, data loss, or eviction, do not infer freshness from endpoint health. The snapshot identity and digest must still match. Disable traffic to known regressed endpoints while recovering; protected requests that cannot find their snapshot fail explicitly. Endpoint changes preserve token and operation identity.

Retain snapshots for at least the accepted context-validity and retry windows, with an agreed safety margin. Server-controlled absolute expiry is bound into context and record. Data disappearing before expiry is unavailability, not evidence that the session expired. Uncertain writes reconcile with the same operation/record identity and origin rather than executing a new mutation in a different region.

## Default latest-local reads

The default `latest` policy reads a local candidate, then verifies it incorporates any carried prior-write requirement. If not, retrieve/wait for the required snapshot; fail at deadline. With no prior-write context, local discovery is eventual. Keep invalid/lost expected context separate from a genuine first read. Record candidate rejection, required-snapshot fallback, and lineage-proof failure independently. Returning a proven descendant advances context under the accepted sequencing mechanism. An incomparable other-device candidate does not bypass the required state.

## Any-version reads

An explicit `any` request reads the local available-snapshot hint without a freshness wait. It may return older/newer valid state or `null`; record the effective policy separately from protected freshness outcomes. Hint publication failures, missing hints, expired hints, and hint/payload memory overhead need monitoring. A hint never authorizes access or proves current revocation state. Any-version results never overwrite protected caller context. Rehearse authenticated cross-device required-context handoff during rollout.

## Monitoring

Separate ordinary exact-ID misses, freshness waits, freshness deadline failures, infrastructure errors, context rejection, expired records, and uncertain writes. Measure local hit rate, propagation wait duration, replication lag, retries, pool saturation, and shard memory/traffic skew. Exclude payloads, bearer identifiers, credentials, and raw context from logs.

Thresholds, paging ownership, traffic targets, and persistence/RPO/RTO remain open. Select them from representative load and service requirements.

## Rollout and rollback

Validate cross-region and cross-group movement in staging, then limit initial traffic. Rollback must preserve envelope/context formats, token verification, caller ordering, and the protected-read contract. If an older adapter cannot preserve context, pause protected operations rather than silently switch to eventual reads. No branch protection, release hook, or deployment permission is configured here.

Record incidents with sanitized context, violated requirement, observed topology, mitigation, and uncertainty. Add regression scenarios and propose follow-up work through a new intent. Immediate global revocation requires a separate authorization mechanism and incident procedure.

## Independent fan-out operations

Monitor per-origin backlog, per-target delivery/verification, oldest undelivered record, replay failures, digest conflicts, expiry handling, and backpressure. Rehearse crash-after-capture, partial fan-out, worker restart, duplicate/reordered delivery, gap-free region catch-up, restore, and safe target removal. A worker must finish obligations after the request process exits. Do not trim the outbox before the accepted delivery/recovery policy permits it. Preserve captured target membership for all-target retries and report ambiguous outcomes without silent shrinkage.
