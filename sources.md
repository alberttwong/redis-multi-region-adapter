# Sources and decision record

Prepared: 2026-11-09. Customer identities and workload branding have intentionally been omitted from the authored documents.

## Precedence

1. Direct user instructions govern scope and target platform: neutral multi-region session consistency, Redis Software 8.x, Active-Active, three shards, the subsequently selected read-your-own-writes target, explicit required-version/any-version read options for Device B, and latest known locally while honoring the caller’s last write as the default.
2. The [AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook) is the primary process reference for intent and requirements artifacts. It does not supply this project's session semantics or select its architecture.
3. The [source presentation](https://docs.google.com/presentation/d/1tuLl3Pg6Zyto0dmEB0aw5u6Z9d2yOaoWv9cvoz4__x4/edit?slide=id.s1_read_hits_misses_20261105#slide=id.s1_read_hits_misses_20261105) supplies technical context. Readable connector content covered all 30 slides, including the linked S1 read slide. This task did not modify the deck or read its linked PRD.
4. Official Redis documentation supplies capability boundaries; new schemas, APIs, and test cases in this repository are design proposals.

The playbook supplies the intent/specification/plan artifact chain, review guidance, verification expectations, and a maintenance feedback path. These files adapt that structure to this project; they do not reproduce the article or claim its example tooling has been installed.

## Deck mapping

| Source slides | Interpretation retained |
| --- | --- |
| 2–4 | Stale values and absent records are distinct; geographic strictness differs from global strictness |
| 5–16 | Replication, acknowledgment, freshness, and packaging are separate choices; a barrier alone does not provide strictness |
| 17–21 | SDK packaging preferred; S1 needs extra authority; owner-cluster affinity conflicts with no-home requirement |
| 22–24 | Epoch-based membership, recovery, and asynchronous foreign-group behavior matter |
| 25–26 | L1, L2, and S1 all remain candidates; illustrative API is not a shipped interface |
| 27 | Cells scale independently of Redis participant membership |
| 28, linked slide | S1 validates current commit before same-cell, same-region, or cross-region lookup; misses are `null`, failures are errors |
| 29–30 | L1/L2 exact-record lookup has no current-revision discovery; L2 adds geographic placement verification |

Earlier slides emphasize a stronger strict geographic target; later slides explicitly reopen the contract choice. The user subsequently selected read-your-own-writes on 2026-11-09. That instruction supersedes the shortlist for current scope. The adapter now adds caller context and protected freshness waits; plain L1 misses do not meet the selected guarantee. L2 and S1 remain historical alternatives only.

## Verified product references

- [Redis Software 8.0.x release notes](https://redis.io/docs/latest/operate/rs/release-notes/rs-8-0-releases/): distinguish product build from database compatibility version.
- [Active-Active overview](https://redis.io/docs/latest/operate/rs/databases/active-active/): CRDT replication and eventual convergence.
- [Causal consistency](https://redis.io/docs/latest/operate/rs/databases/active-active/causal-consistency/): causal operation ordering does not itself establish destination catch-up for a moving caller.
- [WAIT](https://redis.io/docs/latest/commands/wait/): replica acknowledgment limitations; not proof of strong consistency.
- [Transactions](https://redis.io/docs/latest/develop/using-commands/transactions/): local transaction semantics; not a regional distributed transaction manager.

These references were checked on 2026-11-09. No exact-version support matrix, vendor endorsement of S1, or deployed configuration was obtained.

## Decisions and concerns

| ID | State | Decision or question | Suggested reviewer |
| --- | --- | --- | --- |
| D01 | Extended by user | Redis Software 8.x: Active-Active plus a non-Active-Active regional option | Platform owner, unassigned |
| D02 | Assumption | Three primary data shards per regional instance; replicas additional | Platform owner, unassigned |
| D03 | Selected by user, 2026-11-09 | Target read-your-own-writes across regions; defer geographic barriers and strict consistency | Repository owner |
| D04 | Open | Pin Software build, compatibility version, replicas, persistence, and supported commands | Platform owner, unassigned |
| D05 | Open | Define payload size, traffic, latency, timeout, retention, RPO, and RTO | Service owner, unassigned |
| D06 | Deferred | Strict authority, ordering, fencing, and handoff belong to a future strict-consistency scope | Technical lead, unassigned |
| D07 | Open | Define revocation/expiry semantics and session data classification | Security owner, unassigned |
| D08 | Open | Select language, client, packaging, and CI/deployment system | Technical lead, unassigned |
| D09 | Open | Assign artifact reviewers and production release authority | Repository owner |
| D10 | Proposed | Caller-carried immutable snapshot identity; bounded wait at selected endpoint; no automatic remote fallback | Technical lead, unassigned |
| D12 | Requested by user; exact-version interpretation documented; semantics documented 2026-11-09 | Device B can request an exact required version or explicitly accept any local version; authenticated handoff and local hint are proposed implementation details | Repository owner / technical lead |
| D13 | Selected by user, 2026-11-09 | Default to latest known locally while honoring the caller’s last write (RYOW); exact and any remain explicit options | Repository owner |
| D15 | Agreed by user, 2026-11-09 | A reads its acknowledged write locally with context; B without transferred context may read old local state or null. Strict geographic is not selected. | Repository owner |
| D14 | Open | Verify local-candidate lineage/incorporation proof and context advancement under the selected sequencing mechanism | Technical lead, unassigned |
| D11 | Open | Choose secure context transport, write serialization, response ordering, token lifetime, and retry reconciliation | Technical lead, unassigned |

For future acceptance, append artifact revision, reviewer, date, decision, rationale, and review/commit link. Do not fill these with inferred approvals.

## Conversation decisions consolidated

The user selected RYOW, then requested cross-device exact-version or any-version reads. Exact 42 was explained as a specific immutable snapshot, not latest or at-least-42. The user subsequently required latest as the default and explicitly selected “latest known locally, while honoring the caller’s last write (RYOW)” when asked to choose its scope. This latest selection supersedes the earlier proposed required-version default, while preserving exact and any as explicit options. Strict geographic/global consistency remains deferred. Device B’s missing 42 still needs transferred authenticated context to enforce that requirement.

## Additional backend option

The user requested a Redis 8.x option without Active-Active and asked why the adapter cannot write to all regions. It can: backends.md proposes independent regional Redis Software 8.x databases with idempotent adapter-managed fan-out and durable replay. The Software product and three-primary-shard layout are retained from prior requirements. Proposed acknowledgment policies are local-durable-replay by default and all-targets optionally. These are implementation proposals; the user has not selected a capture technology or final persistence contract. Read policy stays latest-local-ryow. Ordinary [Redis replication](https://redis.io/docs/latest/operate/oss_and_stack/management/replication/) is leader/follower replication, not automatic independent writable database synchronization (checked 2026-11-09).
