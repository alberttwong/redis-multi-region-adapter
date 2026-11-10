# Specification: read-your-own-writes across regions

Date: 2026-11-09

Status: consistency target selected by user; detailed design proposed

Inputs: [intent.md](intent.md), [sources.md](sources.md)

Proof: [validation.md](validation.md)

See [consistency.md](consistency.md) for convergence, read consistency, cluster-group scope, and cross-device examples.

## Selected contract

The default read policy is **Session (RYOW)**, named `session`. It selects locally known state while honoring the caller's last acknowledged write. A successful write returns an immutable snapshot and protected context. A default read first considers the selected endpoint's local candidate. With caller context, it may return that candidate only if it matches or provably incorporates the required write. Otherwise it retrieves the required snapshot, waits locally, or returns an explicit freshness error at deadline. Without prior-write context, Session reads perform eventual local discovery.

Explicit `available` reads permit any valid local candidate without the RYOW constraint. Expected snapshot identity is protected middleware context, not a caller-selectable exact-version policy. The internal exact lookup supports Session enforcement; a proven successor may satisfy that enforcement even when the original snapshot is absent.

This contract spans same-cell, same-region, cross-region, and US/EU movement. Other callers may have newer snapshots that this caller has not observed. No global latest-state discovery, per-session linearizability, or linearizable geographic/global commit ordering is promised. All-target placement verification is available only under the explicit independent-backend acknowledgment policy.

The caller lineage is a middleware-managed chain of sequential writes and their following reads, not every device belonging to the same account. A1 and A2 read/write in `us-west-2`, B1 in `us-east-1`, C1 in `us-east-2`, D1 in `eu-west-1`, and E1 in `eu-central-1`. These are six independent clients; none receives another client’s write context or version IDs through direct or out-of-band application communication. Context follows the same caller across requests/regions; cross-device handoff and shared latest-version discovery are outside scope. Reads issued before a write completes are concurrent and do not yet carry its guarantee.

**Session (RYOW)**, named `session`, is the default public read behavior. It does not imply full causal consistency. **Available**, named `available`, is the explicit alternative; exact-version selection is internal plumbing, not a public policy.

Convergence, read consistency, and cluster-group scope are distinct. Explicit `available` has no freshness guarantee; default `session` enforces RYOW when protected caller context is present. Linearizability would require shared ordering per session key, respecting real-time operation order, for all callers in a selected scope. “Linearizable geographic” and “linearizable global” mean geographic-group and all-region scopes of that same deferred guarantee. Group membership alone does not enforce linearizability, restrict RYOW movement, or change acknowledgment participants. Linearizable scopes are explanatory concepts, not supported read-policy settings.

## Session automation and current implementation

Session is intended to remove version handling from business code: middleware retains acknowledged write context, attaches it to later requests from that caller, and invokes the adapter's protected-read checks automatically. That requires a defined context transport and lifecycle; selecting a policy name alone does not supply the guarantee.

The current experimental spike explicitly manages actor context and uses legacy `latest`/`any`/`required` policy names. It is not the proposed production SDK and does not implement automatic middleware context handling. A caller manually passing a version is exercising the underlying mechanism, not receiving the planned automatic integration. The public policies below describe the production design; exact-version selection stays internal there.

## Public read policies

The API supports two read policies. Session is the default; Available is an explicit opt-in. A2, B1, C1, D1, and E1 have no context for A1’s writes. Without their own prior-write requirement, Session performs local discovery and cannot require unknown version 42.

| Read behavior / policy | Request needs | Result at Region B |
| --- | --- | --- |
| **Session (RYOW)** / `session` (default) | Authorized session identity; middleware attaches protected caller context when a prior-write requirement exists | Return a local candidate matching or provably succeeding that write; otherwise internally look up the expected snapshot and wait/recheck eligible candidates or fail |
| **Available** / `available` | Authorized session identity; no version selection | Return a valid local candidate, possibly stale, or `null`; no freshness wait |
| **Linearizable** / `linearizable` (deferred) | A separately designed ordering/coordination protocol within a selected scope | Unsupported in this phase; reject rather than weaken the requested guarantee |

“Version 42” denotes an immutable snapshot identity in a generation/lineage, not a globally ordered integer. Session honors the caller's authenticated context, not the newest completed update across a geographic group or the world. There is no public exact-version or arbitrary minimum-version option.

An independent client cannot discover A1’s unknown version merely by selecting Session. Each client's own writes establish its context, even when clients share a region. A version ID alone does not authorize access. Middleware must reject lost or invalid expected context rather than silently treating the request as a first read.

An application may deliberately choose `available` for a separate request after a Session failure; the adapter never makes that downgrade itself. Available reads do not replace or reduce protected context. Successful reads include actual snapshot identity/generation and effective policy as metadata; these are not public version-selection inputs.

## Scope and terminology

A **snapshot** identifies an immutable session version. Its identity includes session generation and a unique record ID. Numbers such as 42 and 43 are explanatory labels, not a global Redis revision counter.

A **lineage** is a serialized chain of writes. A **proven successor** has authenticated history showing it follows the required write in that lineage. It need not preserve every old field value: a later intentional update may change state. Independent device lineages are incomparable; a cross-device transfer/merge protocol is outside this phase.

A **target** is a regional database in the captured fan-out configuration, not a primary shard, local HA replica, or application cell. A **protected read** is a Session read carrying a prior-write requirement from middleware. See [consistency.md](consistency.md) for the agreed A/B scenario and linearizable geographic comparison.

The baseline pairs reads/writes locally: A1/A2 in `us-west-2`, B1 in `us-east-1`, C1 in `us-east-2`, D1 in `eu-west-1`, E1 in `eu-central-1`. A1/A2 share a logical regional database in the example, with distinct adapter instances and contexts. This is an explicit example-topology assumption, not a claim that every pair of same-region services shares a database.

A2 can discover A1’s published local candidate without a WAN replication wait. A1’s origin acknowledgment does not prove successful discovery-hint publication or establish strict ordering across independent callers. Each client still validates its own context when present. This arrangement changes no policy defaults. The example has five regional databases and fifteen primary shards before replicas. US consists of us-west-2/us-east-1/us-east-2; EU consists of eu-west-1/eu-central-1. Clients and group memberships remain distinct from database shard counts.

## Redis deployment

Support Redis Software 8.x in `active-active` or `independent` distribution mode with three primary data shards per regional database; replica shards are additional. The reference US/EU topology has five instances and therefore fifteen primary data shards before replicas. Cells are service deployment units, not automatically Redis instances. No fixed home cluster is assigned.

Pin the product build, database compatibility version, client, supported commands, replicas, persistence, eviction, and Active-Active settings. Product build and database version are separate checks against the [Redis Software release notes](https://redis.io/docs/latest/operate/rs/release-notes/rs-8-0-releases/).

Active-Active supplies CRDT replication and eventual convergence; see the [product overview](https://redis.io/docs/latest/operate/rs/databases/active-active/). Optional [causal consistency](https://redis.io/docs/latest/operate/rs/databases/active-active/causal-consistency/) preserves causal ordering but does not prove the destination already has a caller's snapshot. The adapter's exact-record check provides that evidence. Neither three shards nor causal configuration replaces context propagation.

## Configuration and mode validation

Keep the following choices separate. These are proposed configuration concepts, not a shipping SDK schema:

- `distribution`: `active-active` or `independent`.
- `acknowledgment`: `local` baseline, or explicit `all-targets` for independent mode.
- `recovery`: explicitly `request-only` or `durable-replay` for independent mode; application recovery is not applicable to native Active-Active transport.
- `readPolicy`: `session` by default or explicit `available` per operation. Reject deferred `linearizable` and unknown policy values; exact-version selection is not a public option.
- Local endpoint, explicit geographic groups (US: us-west-2/us-east-1/us-east-2; EU: eu-west-1/eu-central-1), target list/configuration epoch, and bounded write/read/retry deadlines.

Reject unknown or unsupported combinations before serving requests. Independent mode needs a nonempty authoritative target set including the origin. Replay-enabled mode requires a validated capture/worker configuration; request-only does not require a worker. Active-Active uses origin writes and native transport; all-target adapter verification for that mode is not specified in this phase. All-target success verifies the exact captured set and never silently shrinks it. Group metadata does not itself filter that set: with all five regional targets configured, all-targets waits for all five. Waiting only for the origin group while distributing asynchronously to the foreign group would require a separately specified acknowledgment participant set; it is not silently selected here. Local acknowledgment remains the baseline, with cross-group distribution outside its critical path.

The target is local RYOW regardless of transport. Independent request-only refreshes on the next same-session insert/update; replay optionally preserves historical delivery obligations. [backends.md](backends.md) owns the detailed distribution protocol and [decisions.md](decisions.md) diagrams the options.

## Requirements

| ID | Requirement | Proof |
| --- | --- | --- |
| R01 | Deploy the selected Redis Software 8.x distribution mode with three primary data shards per regional database | V01 |
| R02 | Bind immutable snapshot identity, payload, generation, and expiry; reject conflicting reuse | V02, V06 |
| R03 | Carry protected write context through middleware across all region changes | V03, V08 |
| R04 | Default to Session (RYOW); recheck eligible successors and the internal expected-snapshot lookup while waiting | V03, V05, V19, V24, V28 |
| R05 | Bound local freshness waits; unavailable expected records yield typed errors | V04, V05, V07 |
| R06 | Preserve operation/record identity on uncertain-write reconciliation | V06 |
| R07 | Serialize writes per caller lineage and prevent response/context rollback | V09 |
| R08 | Reject missing, forged, wrong-session, or unsupported required context | V08 |
| R09 | Distinguish ordinary absence, explicit expiry, freshness failure, and infrastructure errors | V04, V10 |
| R10 | Preserve context through endpoint changes and validate readiness/state after restore or target admission | V11, V12, V26 |
| R11 | Define persistence, retention, context lifetime, and retry horizon together | V10, V12 |
| R12 | Bound resource use, distribute sessions over shards, and sanitize telemetry | V13, V15 |
| R13 | State cross-caller and revocation limitations explicitly | V14 |
| R14 | Support default `session` and explicit `available` without implicit downgrade or context rollback; expose no exact-version read policy | V16, V17, V19 |
| R15 | Assume no cross-client context sharing; same-region A2 and remote B1/C1/D1/E1 cannot infer or require A1’s unknown version | V18, V27 |
| R16 | Preserve the agreed A1/A2/B1/C1/D1/E1 local read/write behavior and distinguish it from linearizable geographic consistency | V20, V28 |
| R17 | Independent mode supports explicit request-only or durable-replay recovery; next insert/update distributes only the latest version when replay is off; enabled replay captures obligations durably; all fan-out is idempotent | V21, V23 |
| R18 | Validate policy combinations; distinguish local acceptance from all-target placement acknowledgment; preserve targets on timeout | V22, V25, V29 |

## Proposed adapter API

The language is unresolved; these operations are behavioral descriptions, not existing APIs.

| Operation | Behavior |
| --- | --- |
| `put(sessionId, payload, operationId, context?)` | Create an immutable snapshot at the origin; return record identity and updated protected context on success |
| `get(sessionId, { policy: "session" })` or omitted policy | Session (RYOW); middleware attaches stored authenticated prior-write context internally |
| `get(sessionId, { policy: "available" })` | Return a valid local candidate or `null`, without freshness waiting; preserve stored protected context |

Only `session` and `available` are public policy values in this phase. The expected snapshot identity and exact-record lookup are internal adapter/middleware plumbing, not public `required` or `getRecord` operations. The internal lookup returns a matching envelope or absence to the Session selection loop; it does not itself complete a failed freshness requirement with `null`.

Middleware persists and forwards returned context using an authenticated server-side session or integrity-protected token. Business code calls the normal session API without choosing a version. HTTP error mapping and framework integration remain to be selected.

## Data and context

Store a whole immutable envelope as a serialized String; suggested key: `session:{opaque-session-id}:snapshot:<generation>:<record-id>`. This is a proposed storage envelope for one identified version; request-only fan-out does not require a complete session snapshot or resending earlier versions. Hash tags colocate one session's keys where needed within a regional database, without coordinating regions. Session identifiers distribute across three shards.

The envelope binds schema version, session identity, generation, uniquely generated record ID, payload, digest, and server-assigned absolute expiry. A proposed context binds session identity, generation, record ID, digest, expiry, origin endpoint identity, operation ID, and a middleware-managed lineage sequence. These are application fields, not native Redis metadata. Protect token integrity and bind it to the authenticated caller; a digest alone is not authentication. Never log raw tokens or bearer record IDs.

Use no global revision allocator or mutable pointer as proof of the required version. The context identifies what this caller must see. Unrelated record IDs or numeric counters from different regions cannot be compared as global revisions.

## Local selection for Available reads

Propose a separate local-discovery hint at `session:{opaque-session-id}:available`, containing one complete candidate snapshot envelope with its identity and expiry. A successful origin write publishes this best-effort hint only after storing its immutable snapshot. Its publication/replication need not be atomic with the snapshot because the hint contains the full envelope. An origin hint-publication failure is observable but does not turn an accepted snapshot write into a freshness guarantee for `available` readers.

Read the selected regional instance's hint once, validate identity, session access, integrity, generation policy, and expiry, then return that candidate or `null` if absent/expired. Connectivity or integrity failures remain errors. No scan, replication wait, automatic remote fetch, or newest-version claim is made. A hint may lag, regress, or be missing while immutable snapshots already exist. This is permitted for `available`; the result includes the actual version. Superseded generations must follow the separately accepted session-lifecycle/security policy rather than trusting a stale hint as authorization.

This is an additional proposed schema, not an existing Redis freshness capability. The hint is never itself a protected-read barrier, global latest pointer, or sequencing authority. Default Session reads must additionally prove the candidate satisfies the caller context. Supported command/conflict/expiry behavior must be verified on each pinned backend deployment. It duplicates one payload per session; include that overhead in sizing and benchmarks.

## Session selection and lineage proof

1. Middleware defaults an omitted policy to `session` and attaches any stored prior-write context. A malformed context or an expected context that was lost is an error; an authenticated first read with genuinely no prior context may use eventual local discovery.
2. Read the local candidate envelope. With no prior-write requirement, return that valid candidate or `null` if absent/expired; this cannot discover another device's unpropagated update.
3. With context for 42, return candidate 42, or candidate 43 only with verified evidence that it incorporates 42. In the initial proposal, that evidence is the same protected lineage/generation plus a greater sequence issued under the accepted single-writer sequencing mechanism. Each later lineage write must represent a valid successor to its predecessor. Later updates may intentionally overwrite old values; the history proof establishes ordering, not bitwise payload inclusion. Numeric version comparison, Redis last-write-wins, or publication time alone is insufficient.
4. If the candidate is older, missing, or belongs to an incomparable concurrent lineage, look up exact 42. While waiting within the deadline, recheck both the local candidate and exact 42; a newly arrived proven successor can complete a default Session read even if 42 remains missing. Returning 42 here honors RYOW, even if an incomparable local candidate exists. Do not imply a total newest-version order across devices.
5. If neither the required snapshot nor a proven successor becomes available by the deadline, report snapshot missing. Integrity-invalid records produce an integrity error, never an older successful result. A proven descendant returned by `session` advances protected caller context without permitting rollback. Explicit `available` reads do not reduce that context.

“Latest locally known” therefore means the discovered eligible local candidate under this rule, not a scan or globally ordered maximum of every stored snapshot. Concurrent lineages have no total ordering in this design. A future merge protocol may admit candidates from other lineages only with a proven incorporates relationship. Verifying sequencing/provenance is an open detailed-design requirement; no native Redis revision ordering is assumed.

## Write and retry path

1. Serialize writes in one caller lineage. Create one operation ID and uniquely generated snapshot identity; retain them for retries.
2. Validate caller context and identify the latest version under the accepted lineage protocol, then allocate its next sequence. Do not derive a successor from stale state that omits the required predecessor. If predecessor-dependent update construction is impossible locally, fail explicitly rather than inventing a proof. The sequencing mechanism is a detailed-design decision, not a global session authority.
3. Write the immutable envelope at the selected origin using verified backend-supported commands. In independent mode with durable replay enabled, bind the recoverable fan-out obligation to origin acceptance; deliver copies using the same ID and payload.
4. Establish origin acceptance under the agreed local durability policy. For replay-enabled independent mode, also establish recoverable obligation capture before success. Issue protected context only when the configured acknowledgment condition is satisfied. No remote acknowledgment is required by the default policy. Optional independent `all-targets` acknowledgment additionally verifies every captured participant before success.
5. Persist the new context before issuing a dependent read; reject older responses that try to replace it.

An ambiguous timeout is not success or proof of rollback. Reconcile the same snapshot at the same origin using the same IDs. Do not blindly rerun a non-idempotent business operation elsewhere. If origin status cannot be established, return an uncertain-outcome error. No arbitrary-mutation exactly-once guarantee is claimed. Global identity uniqueness relies on generated IDs and disciplined retries; a local conditional command cannot detect simultaneous same-ID writes at every Active-Active instance. Conflicting identity/content reuse must be rejected or surfaced as an integrity failure, never silently accepted as matching state.

Middleware must define sequencing for shared contexts. The initial proposal permits only one in-flight write per lineage; branching concurrent requests need separate lineages or explicit serialization. Simply placing a signed token in cookies does not prevent out-of-order responses from rolling context back. Integration must demonstrate the sequencing rule before claiming RYOW.

## Internal expected-snapshot lookup

The Session selection loop uses this mechanism when its local candidate cannot satisfy the caller's context. It is not a public policy or a historical-read API.

1. Validate context integrity, caller/session binding, generation, schema, and server-controlled expiry. Lost expected context is an error, not permission to execute an unprotected read.
2. Select the requesting region's endpoint and look up the exact key identified by middleware context.
3. A matching envelope and digest satisfies the expected write. A mismatched identity/digest is an integrity error; older mutable state is never a substitute.
4. On absence, the Session loop polls with bounded backoff/jitter, rechecking both the exact identity and eligible successor candidates. A proven successor can complete the read even if the original identity never arrives.
5. If neither the expected snapshot nor a proven successor is available by the deadline, return `FreshnessUnavailable` with reason `snapshot_missing` and description “snapshot missing.” Connectivity/authentication failures remain separate. Do not return `null` for an expected unexpired snapshot and do not automatically fetch remotely.

An application can separately choose `available`, but the adapter never discards context to obtain availability. There is no public exact-version selector or raw-record lookup.

Expiry is decided from validated server-controlled absolute expiry with an agreed clock-skew policy. An explicitly expired record may return an expired/absent result. A Redis miss before that expiry does not prove expiration. Neither stored snapshot presence nor caller context proves current authorization after another caller's logout.

## Retention and recovery

Retain origin snapshots for the accepted context-validity and retry horizons plus a safety margin. Destination retention governs delivered copies; request-only mode need not deliver every historical snapshot. Define Redis expiry behavior, persistence, backup, and restore procedures for the exact deployment. If acknowledged data is lost or evicted before expiry, fail protected reads explicitly; do not fabricate the required state. Healthy endpoint connectivity does not prove freshness.

Refresh endpoints without losing context or operation identity. Restored/joining participants follow their backend-specific readiness/catch-up rules in backends.md; request-only admission does not promise historical backfill, with snapshot identity and caller-context verification on every protected read. Default local acknowledgment requires no all-member commit protocol. Optional all-target placement acknowledgment captures an authoritative target set/configuration epoch without providing strict commit ordering.

## Outcomes and missing-snapshot wording

Successful reads return payload, actual snapshot identity/generation, and effective policy. A default proven-successor result can advance context safely; explicit Available reads do not reduce the protected floor. Successful writes return snapshot identity and updated context only after the configured acknowledgment condition.

- **Snapshot missing:** neither the expected unexpired snapshot nor a proven successor can be found locally within the deadline. Return `FreshnessUnavailable` with reason `snapshot_missing` and description “snapshot missing.” This reports current absence without asserting whether it arrived previously.
- **Ordinary absence:** an unprotected local lookup has no valid candidate; null is permitted.
- **Expired:** validated server-controlled expiry has passed under the agreed skew policy. A Redis miss alone does not establish expiry.
- **Context/integrity/infrastructure error:** reject invalid context, corrupt identity/content, or connectivity/authentication failure distinctly; none becomes null or a missing snapshot.
- **Partial/uncertain write:** some effects may exist but configured success cannot be confirmed. Preserve original IDs and targets for reconciliation. Do not issue normal successful-write context or imply rollback.

A next insert/update distributes only its latest version. It may refresh current state without restoring exact historical 42. Session can use 43 only with verified successor evidence; the internal lookup of 42 may remain absent without failing that satisfied read. No automatic remote read fallback or downgrade changes these outcomes.

## Open implementation decisions

Language/client, context transport and sequencing, successor proof, collision handling, exact backend commands, capture/worker design when replay is selected, target epoch storage, expiry/skew, retention, payload/token limits, and numeric service levels remain unresolved. They are explicit review gates in [sources.md](sources.md), not completed algorithms.

Linearizable geographic/global authority and native dependency-token support are not assumed. `WAIT` does not provide an Active-Active regional barrier; see the [command reference](https://redis.io/docs/latest/commands/wait/). L1/L2/S1 in the source deck are historical architecture labels, not read-policy names. Optional all-target placement relates to the former L2 barrier and does not select strict consistency.
