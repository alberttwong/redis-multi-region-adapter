# Specification: read-your-own-writes across regions

Date: 2026-11-09

Status: consistency target selected by user; detailed design proposed

Inputs: [intent.md](intent.md), [sources.md](sources.md)

Proof: [validation.md](validation.md)

See [consistency.md](consistency.md) for the four consistency levels and cross-device examples.

## Selected contract

The default read policy is **latest known locally while honoring the caller's last acknowledged write (RYOW)**. A successful write returns an immutable snapshot and protected context. A default read first considers the selected endpoint's local candidate. With caller context, it may return that candidate only if it matches or provably incorporates the required write. Otherwise it retrieves the required snapshot, waits locally, or returns an explicit freshness error at deadline. Without prior-write context, latest-local reads have eventual semantics.

Explicit `required` reads request one exact snapshot, even when a newer snapshot exists. Explicit `any` reads permit any valid local candidate without the RYOW freshness constraint. These policies are distinct; exact-version reads do not redefine the default.
This contract spans same-cell, same-region, cross-region, and US/EU movement. Other callers may have newer snapshots that this caller has not observed. No global latest-state discovery, per-session linearizability, all-member placement barrier, or strict geographic/global commit ordering is promised.

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

## Agreed scenario and strict geographic comparison

Assume A's write of 42 has completed before either read begins, B's region still has 41 or no record, and both regions belong to the same geographic group for the strict comparison. Both devices use the default `latest` policy.

| Read | Selected design: latest local + RYOW | Strict geographic alternative |
| --- | --- | --- |
| Device A reads Region A with write context | Return 42 or a proven local successor; otherwise fail explicitly | Reflect 42 or a later committed update, or fail |
| Device B reads Region B without context for 42 | Local 41 or `null` is permitted; after replication, 42 can become the local candidate | Must reflect 42 or a later committed update; stale success and an absent result caused solely by propagation lag are forbidden |
| Device B reads Region B with authenticated context for 42 | Return 42 or a proven local successor; wait locally if needed, then return freshness error at deadline | Same minimum completed-write obligation applies regardless of caller context |

The selected guarantee follows caller context. Strict geographic establishes one per-session linearizable history for all callers in the group, so B does not need A's token to observe a completed update. It requires a shared ordering and safe-read/recovery protocol beyond replication and adapter polling. A geographic write-copy barrier alone is insufficient. Regions in different geographic groups would need a separately defined cross-group guarantee; strict geographic alone does not make foreign projections current.

The user agreed to this scenario. Device B does not automatically inherit Device A's context. Default local reads can therefore remain stale for other devices; this is accepted behavior, not an implementation defect. Immediate cross-device revocation is not supplied by the selected guarantee.

## Redis deployment

Use Redis Software 8.x Active-Active with three primary data shards per regional database instance; replica shards are additional. The reference US/EU topology has five instances and therefore fifteen primary data shards before replicas. Cells are service deployment units, not automatically Redis instances. No fixed home cluster is assigned.

Pin the product build, database compatibility version, client, supported commands, replicas, persistence, eviction, and Active-Active settings. Product build and database version are separate checks against the [Redis Software release notes](https://redis.io/docs/latest/operate/rs/release-notes/rs-8-0-releases/).

Active-Active supplies CRDT replication and eventual convergence; see the [product overview](https://redis.io/docs/latest/operate/rs/databases/active-active/). Optional [causal consistency](https://redis.io/docs/latest/operate/rs/databases/active-active/causal-consistency/) preserves causal ordering but does not prove the destination already has a caller's snapshot. The adapter's exact-record check provides that evidence. Neither three shards nor causal configuration replaces context propagation.

## Requirements

| ID | Requirement | Proof |
| --- | --- | --- |
| R01 | Deploy the selected Redis Software 8.x Active-Active three-primary-shard layout | V01 |
| R02 | Bind immutable snapshot identity, payload, generation, and expiry; reject conflicting reuse | V02, V06 |
| R03 | Carry protected write context through middleware across all region changes | V03, V08 |
| R04 | Default to latest-local subject to RYOW; return exact snapshot when explicitly required; never accept older state on a protected read | V03, V05, V19 |
| R05 | Bound local freshness waits; unavailable expected records yield typed errors | V04, V05, V07 |
| R06 | Preserve operation/record identity on uncertain-write reconciliation | V06 |
| R07 | Serialize writes per caller lineage and prevent response/context rollback | V09 |
| R08 | Reject missing, forged, wrong-session, or unsupported required context | V08 |
| R09 | Distinguish ordinary absence, explicit expiry, freshness failure, and infrastructure errors | V04, V10 |
| R10 | Preserve context through endpoint changes and validate exact snapshots after restore | V11, V12 |
| R11 | Define persistence, retention, context lifetime, and retry horizon together | V10, V12 |
| R12 | Bound resource use, distribute sessions over shards, and sanitize telemetry | V13, V15 |
| R13 | State cross-caller and revocation limitations explicitly | V14 |
| R14 | Support default latest-local and explicit required/any policies without implicit downgrade or context rollback | V16, V17, V19 |
| R15 | Transfer required-version context to authorized Device B through authenticated handoff | V18 |
| R16 | Preserve the agreed A-local/B-local behavior and distinguish it from strict geographic consistency | V20 |

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

This is an additional proposed schema, not an existing Redis freshness capability. The hint is never itself a protected-read barrier, global latest pointer, or sequencing authority. Default latest-local reads must additionally prove the candidate satisfies the caller context. Supported command/conflict/expiry behavior must be verified on the pinned Active-Active deployment. It duplicates one payload per session; include that overhead in sizing and benchmarks.

## Default latest-local selection and lineage proof

1. Middleware defaults an omitted policy to `latest` and attaches any stored prior-write context. A malformed context or an expected context that was lost is an error; an authenticated first read with genuinely no prior context may use eventual local discovery.
2. Read the local candidate envelope. With no prior-write requirement, return that valid candidate or `null` if absent/expired; this cannot discover another device's unpropagated update.
3. With context for 42, return candidate 42, or candidate 43 only with verified evidence that it incorporates 42. In the initial proposal, that evidence is the same protected lineage/generation plus a greater sequence issued under the accepted single-writer sequencing mechanism. Each later lineage write must be based on its predecessor, not an unrelated payload. Numeric version comparison, Redis last-write-wins, or publication time alone is insufficient.
4. If the candidate is older, missing, or belongs to an incomparable concurrent lineage, look up exact 42 and wait within the deadline if necessary. Returning 42 here honors RYOW, even if an incomparable local candidate exists. Do not imply a total newest-version order across devices.
5. A missing/integrity-invalid required snapshot yields a typed failure, never an older successful result. A proven descendant returned by `latest` advances protected caller context without permitting rollback. Explicit `any` and historical exact reads do not reduce that context.

“Latest locally known” therefore means the discovered eligible local candidate under this rule, not a scan or globally ordered maximum of every stored snapshot. Concurrent lineages have no total ordering in this design. A future merge protocol may admit candidates from other lineages only with a proven incorporates relationship. Verifying sequencing/provenance is an open detailed-design requirement; no native Redis revision ordering is assumed.

## Write and retry path

1. Serialize writes in one caller lineage. Create one operation ID and uniquely generated snapshot identity; retain them for retries.
2. Validate caller context and allocate its next lineage sequence in the middleware's sequencing mechanism. The mechanism is a detailed-design decision, not a global session authority.
3. Write the immutable envelope once at the selected origin using verified Active-Active-supported commands.
4. Establish origin acceptance under the agreed local durability policy, then issue protected context together with the success response. No remote acknowledgment is required.
5. Persist the new context before issuing a dependent read; reject older responses that try to replace it.

An ambiguous timeout is not success or proof of rollback. Reconcile the same snapshot at the same origin using the same IDs. Do not blindly rerun a non-idempotent business operation elsewhere. If origin status cannot be established, return an uncertain-outcome error. No arbitrary-mutation exactly-once guarantee is claimed. Global identity uniqueness relies on generated IDs and disciplined retries; a local conditional command cannot detect simultaneous same-ID writes at every Active-Active instance. Conflicting identity/content reuse must be rejected or surfaced as an integrity failure, never silently accepted as matching state.

Middleware must define sequencing for shared contexts. The initial proposal permits only one in-flight write per lineage; branching concurrent requests need separate lineages or explicit serialization. Simply placing a signed token in cookies does not prevent out-of-order responses from rolling context back. Integration must demonstrate the sequencing rule before claiming RYOW.

## Explicit required-version read path

1. Validate context integrity, caller/session binding, generation, schema, and server-controlled expiry. Missing required context is a context error, not permission to execute an eventual read.
2. Select the requesting region's eligible endpoint and look up the exact snapshot key.
3. On a matching envelope and digest, return its payload. An older mutable session value is never a substitute.
4. On absence, poll with bounded backoff/jitter until the read deadline. Mismatched identity/digest is an integrity error rather than successful data.
5. At deadline, return `FreshnessUnavailable`. Connectivity/authentication failures remain distinct infrastructure errors. Do not return `null` for an expected unexpired snapshot and do not automatically fetch remotely.

A request can explicitly use the `any` policy or `getRecord`. The latter returns `null` on a genuine endpoint miss. Both have eventual semantics; `any` discovers a session candidate, whereas `getRecord` looks up a supplied exact identity. Context must not be silently discarded to obtain availability.

Expiry is decided from validated server-controlled absolute expiry with an agreed clock-skew policy. An explicitly expired record may return an expired/absent result. A Redis miss before that expiry does not prove expiration. Neither stored snapshot presence nor caller context proves current authorization after another caller's logout.

## Retention and recovery

Retain snapshots for the accepted context-validity and retry horizons plus a safety margin. Define Redis expiry behavior, persistence, backup, and restore procedures for the exact deployment. If acknowledged data is lost or evicted before expiry, fail protected reads explicitly; do not fabricate the required state. Healthy endpoint connectivity does not prove freshness.

Refresh endpoints without losing context or operation identity. Restored/joining participants undergo supported product catch-up and readiness checks, with snapshot identity and caller-context verification on every protected read. The adapter requires no all-member epoch-based commit protocol in this phase.

## Deferred guarantees and concerns

L1 from the deck allows propagation misses and therefore does not alone satisfy this protected-read contract. L2's all-member write barrier and S1's strict commit authority are deferred. Native replication dependency tokens are not assumed. `WAIT` is not an Active-Active cross-region freshness barrier; see the [command reference](https://redis.io/docs/latest/commands/wait/).

Before implementation, resolve language/client, sequencing and context transport, collision/retry details, supported command matrix, persistence, retention, expiry/skew, deadlines, token size, and security ownership. RYOW was selected by the user on 2026-11-09; no unresolved strict authority choice blocks this phase.
