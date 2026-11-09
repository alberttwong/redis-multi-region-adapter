# Specification: read-your-own-writes across regions

Date: 2026-11-09

Status: consistency target selected by user; detailed design proposed

Inputs: [intent.md](intent.md), [sources.md](sources.md)

Proof: [validation.md](validation.md)

See [consistency.md](consistency.md) for the four consistency levels and cross-device examples.

## Selected contract

The default read policy is **latest known locally while honoring the caller's last acknowledged write (RYOW)**. A successful write returns an immutable snapshot and protected context. A default read first considers the selected endpoint's local candidate. With caller context, it may return that candidate only if it matches or provably incorporates the required write. Otherwise it retrieves the required snapshot, waits locally, or returns an explicit freshness error at deadline. Without prior-write context, latest-local reads have eventual semantics.

Explicit `required` reads request one exact snapshot, even when a newer snapshot exists. Explicit `any` reads permit any valid local candidate without the RYOW freshness constraint. These policies are distinct; exact-version reads do not redefine the default.
This contract spans same-cell, same-region, cross-region, and US/EU movement. Other callers may have newer snapshots that this caller has not observed. No global latest-state discovery, per-session linearizability, or strict geographic/global commit ordering is promised. All-target placement verification is available only under the explicit independent-backend acknowledgment policy.

The caller lineage is a middleware-managed chain of sequential writes and their following reads, not every device belonging to the same account. A different device does not inherit guarantees unless context is explicitly transferred through an authenticated mechanism. Reads issued before a write completes are concurrent and do not yet carry its guarantee.

## Explicit read policies

Device B can choose among three policies per request:

| Policy | Request needs | Result at Region B |
| --- | --- | --- |
| `latest` (default; latest locally known eligible state) | Authorized session identity; caller's protected context when it has a prior-write requirement | Return a local candidate proven to include that write; otherwise retrieve/wait for the required snapshot or fail |
| `required` (exact version) | Authenticated context identifying exact version 42 | Return exactly 42 when present; otherwise wait locally until deadline, then return `FreshnessUnavailable` |
| `any` (explicit opt-in) | Authorized session identity; no required version | Return a locally selected valid snapshot, possibly older or newer than 42; return `null` if none is available |

Here, “version 42” denotes an immutable snapshot identity in an identified generation/lineage, not a globally ordered integer. `required` means exactly 42. The default `latest` means local discovery constrained by the caller's RYOW context, not the newest completed update across a geographic group or the world. A separate arbitrary “at least 42” API is deferred; the default's freshness floor is the caller's authenticated context.

For cross-device required reads, an authenticated handoff must issue context usable by authorized Device B. Do not simply reuse a token bound exclusively to Device A. Possession of a version ID alone does not authorize session access. Missing handoff context in `required` mode is an error; it must not select `any` automatically.

An application may deliberately choose `any` for a separate request after a required-read failure, but the adapter never makes that downgrade itself. An `any` read does not replace or reduce the caller's protected context. A deliberately requested historical exact read likewise does not reduce the context used for subsequent default latest reads. Return actual snapshot identity/generation and effective read policy alongside a successful payload so applications can distinguish the outcome without implementing freshness checks.

## Scope and terminology

A **snapshot** is a complete immutable session state. Its identity includes session generation and a unique record ID. Numbers such as 42 and 43 are explanatory labels, not a global Redis revision counter.

A **lineage** is a serialized chain of writes. A **proven successor** has authenticated history showing it follows the required write in that lineage. It need not preserve every old field value: a later intentional update may change state. Independent device lineages are incomparable unless an accepted transfer/merge protocol proves otherwise.

A **target** is a regional database in the captured fan-out configuration, not a primary shard, local HA replica, or application cell. A **protected read** carries a prior-write or exact-version requirement. See [consistency.md](consistency.md) for the agreed A/B scenario and strict geographic comparison.

## Redis deployment

Support Redis Software 8.x in `active-active` or `independent` distribution mode with three primary data shards per regional database; replica shards are additional. The reference US/EU topology has five instances and therefore fifteen primary data shards before replicas. Cells are service deployment units, not automatically Redis instances. No fixed home cluster is assigned.

Pin the product build, database compatibility version, client, supported commands, replicas, persistence, eviction, and Active-Active settings. Product build and database version are separate checks against the [Redis Software release notes](https://redis.io/docs/latest/operate/rs/release-notes/rs-8-0-releases/).

Active-Active supplies CRDT replication and eventual convergence; see the [product overview](https://redis.io/docs/latest/operate/rs/databases/active-active/). Optional [causal consistency](https://redis.io/docs/latest/operate/rs/databases/active-active/causal-consistency/) preserves causal ordering but does not prove the destination already has a caller's snapshot. The adapter's exact-record check provides that evidence. Neither three shards nor causal configuration replaces context propagation.

## Configuration and mode validation

Keep the following choices separate. These are proposed configuration concepts, not a shipping SDK schema:

- `distribution`: `active-active` or `independent`.
- `acknowledgment`: `local` baseline, or explicit `all-targets` for independent mode.
- `recovery`: explicitly `request-only` or `durable-replay` for independent mode; application recovery is not applicable to native Active-Active transport.
- `readPolicy`: `latest` by default, explicit `required` or `any` per operation.
- Local endpoint, geographic labels, target list/configuration epoch, and bounded write/read/retry deadlines.

Reject unknown or unsupported combinations before serving requests. Independent mode needs a nonempty authoritative target set including the origin. Replay-enabled mode requires a validated capture/worker configuration; request-only does not require a worker. Active-Active uses origin writes and native transport; all-target adapter verification for that mode is not specified in this phase. All-target success verifies the exact captured set and never silently shrinks it.

The target is local RYOW regardless of transport. Independent request-only refreshes on the next same-session insert/update; replay optionally preserves historical delivery obligations. [backends.md](backends.md) owns the detailed distribution protocol and [decisions.md](decisions.md) diagrams the options.

## Requirements

| ID | Requirement | Proof |
| --- | --- | --- |
| R01 | Deploy the selected Redis Software 8.x distribution mode with three primary data shards per regional database | V01 |
| R02 | Bind immutable snapshot identity, payload, generation, and expiry; reject conflicting reuse | V02, V06 |
| R03 | Carry protected write context through middleware across all region changes | V03, V08 |
| R04 | Default to latest-local subject to RYOW; recheck successors while waiting; exact reads never substitute another version | V03, V05, V19, V24 |
| R05 | Bound local freshness waits; unavailable expected records yield typed errors | V04, V05, V07 |
| R06 | Preserve operation/record identity on uncertain-write reconciliation | V06 |
| R07 | Serialize writes per caller lineage and prevent response/context rollback | V09 |
| R08 | Reject missing, forged, wrong-session, or unsupported required context | V08 |
| R09 | Distinguish ordinary absence, explicit expiry, freshness failure, and infrastructure errors | V04, V10 |
| R10 | Preserve context through endpoint changes and validate readiness/state after restore or target admission | V11, V12, V26 |
| R11 | Define persistence, retention, context lifetime, and retry horizon together | V10, V12 |
| R12 | Bound resource use, distribute sessions over shards, and sanitize telemetry | V13, V15 |
| R13 | State cross-caller and revocation limitations explicitly | V14 |
| R14 | Support default latest-local and explicit required/any policies without implicit downgrade or context rollback | V16, V17, V19 |
| R15 | Transfer required-version context to authorized Device B through authenticated handoff | V18 |
| R16 | Preserve the agreed A-local/B-local behavior and distinguish it from strict geographic consistency | V20 |
| R17 | Independent mode supports explicit request-only or durable-replay recovery; next insert/update repeats complete-snapshot fan-out when replay is off; enabled replay captures obligations durably; all fan-out is idempotent | V21, V23 |
| R18 | Validate policy combinations; distinguish local acceptance from all-target placement acknowledgment; preserve targets on timeout | V22, V25 |

## Proposed adapter API

The language is unresolved; these operations are behavioral descriptions, not existing APIs.

| Operation | Behavior |
| --- | --- |
| `put(sessionId, payload, operationId, context?)` | Create an immutable snapshot at the origin; return record identity and updated protected context on success |
| `get(sessionId, { policy: "latest", context? })` or omitted policy | Default latest-local read, constrained by authenticated prior-write context when present |
| `get(sessionId, { policy: "required", context })` | Explicit exact-snapshot read; context is mandatory |
| `get(sessionId, { policy: "any" })` | Read a locally available snapshot via a session-local hint; no freshness wait or required-version guarantee |
| `getRecord(recordId)` | Unprotected eventual exact-ID lookup; hit or `null`, with infrastructure errors separate |

Keep protected and unprotected operations explicit. Middleware persists and forwards returned context using an authenticated server-side session or integrity-protected token. Business code continues to call a normal session API. HTTP error mapping and framework integration remain to be selected.

## Data and context

Store a whole immutable envelope as a serialized String; suggested key: `session:{opaque-session-id}:snapshot:<generation>:<record-id>`. Whole-record access avoids mutable field merges for the required snapshot. Hash tags colocate one session's keys where needed within a regional database, without coordinating regions. Session identifiers distribute across three shards.

The envelope binds schema version, session identity, generation, uniquely generated record ID, payload, digest, and server-assigned absolute expiry. A proposed context binds session identity, generation, record ID, digest, expiry, origin endpoint identity, operation ID, and a middleware-managed lineage sequence. These are application fields, not native Redis metadata. Protect token integrity and bind it to the authenticated caller; a digest alone is not authentication. Never log raw tokens or bearer record IDs.

Use no global revision allocator or mutable pointer as proof of the required version. The context identifies what this caller must see. Unrelated record IDs or numeric counters from different regions cannot be compared as global revisions.

## Local selection for any-version reads

Propose a separate local-discovery hint at `session:{opaque-session-id}:available`, containing one complete candidate snapshot envelope with its identity and expiry. A successful origin write publishes this best-effort hint only after storing its immutable snapshot. Its publication/replication need not be atomic with the snapshot because the hint contains the full envelope. An origin hint-publication failure is observable but does not turn an accepted snapshot write into a freshness guarantee for `any` readers.

Read the selected regional instance's hint once, validate identity, session access, integrity, generation policy, and expiry, then return that candidate or `null` if absent/expired. Connectivity or integrity failures remain errors. No scan, replication wait, automatic remote fetch, or newest-version claim is made. A hint may lag, regress, or be missing while immutable snapshots already exist. This is permitted for `any`; the result includes the actual version. Superseded generations must follow the separately accepted session-lifecycle/security policy rather than trusting a stale hint as authorization.

This is an additional proposed schema, not an existing Redis freshness capability. The hint is never itself a protected-read barrier, global latest pointer, or sequencing authority. Default latest-local reads must additionally prove the candidate satisfies the caller context. Supported command/conflict/expiry behavior must be verified on each pinned backend deployment. It duplicates one payload per session; include that overhead in sizing and benchmarks.

## Default latest-local selection and lineage proof

1. Middleware defaults an omitted policy to `latest` and attaches any stored prior-write context. A malformed context or an expected context that was lost is an error; an authenticated first read with genuinely no prior context may use eventual local discovery.
2. Read the local candidate envelope. With no prior-write requirement, return that valid candidate or `null` if absent/expired; this cannot discover another device's unpropagated update.
3. With context for 42, return candidate 42, or candidate 43 only with verified evidence that it incorporates 42. In the initial proposal, that evidence is the same protected lineage/generation plus a greater sequence issued under the accepted single-writer sequencing mechanism. Each later lineage write must represent the next full state after its predecessor. Later updates may intentionally overwrite old values; the history proof establishes ordering, not bitwise payload inclusion. Numeric version comparison, Redis last-write-wins, or publication time alone is insufficient.
4. If the candidate is older, missing, or belongs to an incomparable concurrent lineage, look up exact 42. While waiting within the deadline, recheck both the local candidate and exact 42; a newly arrived proven successor can complete a default latest read even if 42 remains missing. Returning 42 here honors RYOW, even if an incomparable local candidate exists. Do not imply a total newest-version order across devices.
5. If neither the required snapshot nor a proven successor becomes available by the deadline, report snapshot missing. Integrity-invalid records produce an integrity error, never an older successful result. A proven descendant returned by `latest` advances protected caller context without permitting rollback. Explicit `any` and historical exact reads do not reduce that context.

“Latest locally known” therefore means the discovered eligible local candidate under this rule, not a scan or globally ordered maximum of every stored snapshot. Concurrent lineages have no total ordering in this design. A future merge protocol may admit candidates from other lineages only with a proven incorporates relationship. Verifying sequencing/provenance is an open detailed-design requirement; no native Redis revision ordering is assumed.

## Write and retry path

1. Serialize writes in one caller lineage. Create one operation ID and uniquely generated snapshot identity; retain them for retries.
2. Validate caller context and construct the complete next session state under the accepted lineage protocol, then allocate its next sequence. Do not derive a successor from stale state that omits the required predecessor. If predecessor-dependent update construction is impossible locally, fail explicitly rather than inventing a proof. The sequencing mechanism is a detailed-design decision, not a global session authority.
3. Write the immutable envelope at the selected origin using verified backend-supported commands. In independent mode with durable replay enabled, bind the recoverable fan-out obligation to origin acceptance; deliver copies using the same ID and payload.
4. Establish origin acceptance under the agreed local durability policy. For replay-enabled independent mode, also establish recoverable obligation capture before success. Issue protected context only when the configured acknowledgment condition is satisfied. No remote acknowledgment is required by the default policy. Optional independent `all-targets` acknowledgment additionally verifies every captured participant before success.
5. Persist the new context before issuing a dependent read; reject older responses that try to replace it.

An ambiguous timeout is not success or proof of rollback. Reconcile the same snapshot at the same origin using the same IDs. Do not blindly rerun a non-idempotent business operation elsewhere. If origin status cannot be established, return an uncertain-outcome error. No arbitrary-mutation exactly-once guarantee is claimed. Global identity uniqueness relies on generated IDs and disciplined retries; a local conditional command cannot detect simultaneous same-ID writes at every Active-Active instance. Conflicting identity/content reuse must be rejected or surfaced as an integrity failure, never silently accepted as matching state.

Middleware must define sequencing for shared contexts. The initial proposal permits only one in-flight write per lineage; branching concurrent requests need separate lineages or explicit serialization. Simply placing a signed token in cookies does not prevent out-of-order responses from rolling context back. Integration must demonstrate the sequencing rule before claiming RYOW.

## Explicit required-version read path

1. Validate context integrity, caller/session binding, generation, schema, and server-controlled expiry. Missing required context is a context error, not permission to execute an eventual read.
2. Select the requesting region's eligible endpoint and look up the exact snapshot key.
3. On a matching envelope and digest, return its payload. An older mutable session value is never a substitute.
4. On absence, poll with bounded backoff/jitter until the read deadline. Mismatched identity/digest is an integrity error rather than successful data.
5. At deadline, return `FreshnessUnavailable` with reason `snapshot_missing` and the plain-language description “snapshot missing.” Connectivity/authentication failures remain distinct infrastructure errors. Do not return `null` for an expected unexpired snapshot and do not automatically fetch remotely.

A request can explicitly use the `any` policy or `getRecord`. The latter returns `null` on a genuine endpoint miss. Both have eventual semantics; `any` discovers a session candidate, whereas `getRecord` looks up a supplied exact identity. Context must not be silently discarded to obtain availability.

Expiry is decided from validated server-controlled absolute expiry with an agreed clock-skew policy. An explicitly expired record may return an expired/absent result. A Redis miss before that expiry does not prove expiration. Neither stored snapshot presence nor caller context proves current authorization after another caller's logout.

## Retention and recovery

Retain origin snapshots for the accepted context-validity and retry horizons plus a safety margin. Destination retention governs delivered copies; request-only mode need not deliver every historical snapshot. Define Redis expiry behavior, persistence, backup, and restore procedures for the exact deployment. If acknowledged data is lost or evicted before expiry, fail protected reads explicitly; do not fabricate the required state. Healthy endpoint connectivity does not prove freshness.

Refresh endpoints without losing context or operation identity. Restored/joining participants follow their backend-specific readiness/catch-up rules in backends.md; request-only admission does not promise historical backfill, with snapshot identity and caller-context verification on every protected read. Default local acknowledgment requires no all-member commit protocol. Optional all-target placement acknowledgment captures an authoritative target set/configuration epoch without providing strict commit ordering.

## Outcomes and missing-snapshot wording

Successful reads return payload, actual snapshot identity/generation, and effective policy. A default proven-successor result can advance context safely; explicit any or historical exact reads do not reduce the protected floor. Successful writes return snapshot identity and updated context only after the configured acknowledgment condition.

- **Snapshot missing:** expected unexpired state cannot be found locally within the deadline. Return `FreshnessUnavailable` with reason `snapshot_missing` and description “snapshot missing.” This reports current absence without asserting whether it arrived previously.
- **Ordinary absence:** an unprotected local lookup has no valid candidate; null is permitted.
- **Expired:** validated server-controlled expiry has passed under the agreed skew policy. A Redis miss alone does not establish expiry.
- **Context/integrity/infrastructure error:** reject invalid context, corrupt identity/content, or connectivity/authentication failure distinctly; none becomes null or a missing snapshot.
- **Partial/uncertain write:** some effects may exist but configured success cannot be confirmed. Preserve original IDs and targets for reconciliation. Do not issue normal successful-write context or imply rollback.

A next insert/update sends its own new complete snapshot. It may refresh current state without restoring exact historical 42. Default latest can use 43 only with verified successor evidence; exact 42 remains missing. No automatic remote read fallback or downgrade changes these outcomes.

## Open implementation decisions

Language/client, context transport and sequencing, successor proof, collision handling, exact backend commands, capture/worker design when replay is selected, target epoch storage, expiry/skew, retention, payload/token limits, and numeric service levels remain unresolved. They are explicit review gates in [sources.md](sources.md), not completed algorithms.

Strict geographic/global authority and native dependency-token support are not assumed. `WAIT` does not provide an Active-Active regional barrier; see the [command reference](https://redis.io/docs/latest/commands/wait/). L1/L2/S1 in the source deck are historical architecture labels, not read-policy names. Optional all-target placement relates to the former L2 barrier and does not select strict consistency.
