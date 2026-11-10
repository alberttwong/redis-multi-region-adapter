# Sources and decisions

Updated: 2026-11-10. Authored documents omit customer identities and workload branding. This file records provenance and decision status; [spec.md](spec.md) owns behavior.

## Precedence and artifact ownership

Direct user instructions take precedence over the source deck and process guidance. The [AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook) guides the intent/specification/plan chain, verification, review, and maintenance feedback. It does not choose session semantics or install controls.

Repository Markdown is the design source of truth. intent.md states the outcome; spec.md defines behavior; backends.md defines distribution obligations; consistency.md explains the guarantees; decisions.md illustrates combinations. plan.md, validation.md, and operations.md define proposed implementation, proof, and operation. CLAUDE.md and REVIEW.md summarize instructions without overriding the specification.

## Technical provenance

The [source presentation](https://docs.google.com/presentation/d/1tuLl3Pg6Zyto0dmEB0aw5u6Z9d2yOaoWv9cvoz4__x4/edit?slide=id.s1_read_hits_misses_20261105#slide=id.s1_read_hits_misses_20261105) was read through connector text covering all 30 slides, including the linked S1 read slide. Its linked PRD was not read, and the deck was not modified.

Slides 2–4 distinguish stale/absent state and consistency levels; 5–16 separate replication, acknowledgment, freshness, and packaging; 17–24 discuss SDK packaging, strict authority, membership, and failure costs; 25–30 retain L1/L2/S1 alternatives and describe cells, exact snapshots, and misses. Those are historical source choices. Later user decisions below supersede the shortlist: strict S1 is deferred, while optional all-target placement resembles the earlier L2 barrier.

Product references previously checked on 2026-11-09:

- [Redis Software releases](https://redis.io/docs/latest/operate/rs/release-notes/rs-8-0-releases/): product build and database compatibility version are separate checks.
- [Active-Active](https://redis.io/docs/latest/operate/rs/databases/active-active/) and [causal consistency](https://redis.io/docs/latest/operate/rs/databases/active-active/causal-consistency/): convergence and causal ordering do not establish a destination's current freshness.
- [Replication](https://redis.io/docs/latest/operate/oss_and_stack/management/replication/): primary/replica replication is not synchronization between independent writable databases.
- [Benchmarking](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/benchmarks/) and [latency diagnosis](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/latency/): measurement guidance for the planning model in latency.md; no project benchmark results (checked 2026-11-09).
- [WAIT](https://redis.io/docs/latest/commands/wait/) and [transactions](https://redis.io/docs/latest/develop/using-commands/transactions/): do not supply the proposed geographic strict protocol.

MongoDB [read concerns](https://www.mongodb.com/docs/manual/reference/read-concern/) were terminology references, not equivalent capabilities across independent Redis clusters. This project's revised Available policy races group members and is not MongoDB's instance-local `available` read concern. The earlier RYOW/Session option was removed; legacy prototype results retain their original labels.

No production support matrix, approved linearizable protocol, or production service levels are established. The legacy spike has a recorded deployment and measurements; candidate storage, group-racing reads, and production fan-out remain proposed application design. Background repair workers are outside production scope.

## Selected decisions

Architecture guidance clarified on 2026-11-09: **both Active-Active and independent regional clusters are supported**. Neither backend is recommended universally; Active-Active supplies additional native capabilities. Independent fan-out provides a reduced capability subset; the adapter adds the same explicit Local/Available read contract on either backend. Choose based on capabilities, operations, and total cost without assuming either backend is cheaper.

All user decisions below were made on 2026-11-09. They select scope, not every proposed implementation mechanism.

- Redis Software 8.x, with Active-Active and an additional non-Active-Active option. The independent regional fan-out architecture is the proposed implementation of that additional option.
- Three shards; interpreting this as three primary shards per regional database, with replicas additional, remains a sizing assumption to confirm. Six clients in five regional databases therefore use fifteen primary shards in the example, with A1/A2 sharing the west regional database.
- Default **Available** (`available`) with the proposed monotonic modifier off (`false`): race every selected group cluster concurrently, including local, returning first valid non-null value. Return null if all replies are null or the shared deadline expires without a value. An early null does not win. Explicit **Local** (`local`) queries only local. No latest-state, RYOW, or quorum guarantee is selected.
- Session reads and automatic caller-context/lineage enforcement are removed from the production scope. Exact identities remain distribution/retry plumbing, not public reads. `greedy` was a temporary name for the new Available race, not a separate policy.
- Remove Causal as a read option and custom causal protocol workstream; native Active-Active causal consistency remains optional backend configuration. Model **Monotonic** as a proposed boolean option (`monotonic: true`, default false) on Local/Available on either backend, not a standalone policy: automatically carry each caller's last successful tracked read floor and guarantee **last-observed freshness**, without claiming latest-completed-write freshness, a staleness-age bound, or RYOW. The freshness column must name the kind of guarantee rather than use an ambiguous binary yes/no. Keep both Linearizable implementations with the same full real-time per-key target guarantee and **slow++** planning ratings for both reads and writes, without a measured-performance or lower-bound claim. All new SDK/custom protocol integrations remain unimplemented; Available remains default and Session/exact-version selectors stay removed.
- A1/A2 read/write in `us-west-2`, B1 in `us-east-1`, C1 in `us-east-2`, D1 in `eu-west-1`, and E1 in `eu-central-1`. US groups the three US regions; EU groups the two EU regions. All are independent clients with no application write-context exchange. This extends earlier client examples with the revised Available default described above. Group membership alone does not choose which targets a write waits for; an origin-group-only barrier remains a separate design choice. The example assumes A1/A2 share one logical regional database; verify actual endpoint/cell placement. Redis replication/adapter fan-out transports data. Read groups define Available probes and do not alter write acknowledgment sets.
- Delivery recovery follows the backend: independent clusters have no background repair; Active-Active is Redis-managed. Remove the separate recovery selector and durable replay option from production scope. Local acknowledgment remains baseline; all-target verification is explicit.
- Each independent same-session insert/update distributes its current version as normal write fan-out. This is not a separate next-write refresh mode. Historical gaps need not be restored, and without another write a missed delivery may stay unrepaired indefinitely. Describe an absent expected exact snapshot as **snapshot missing**.
- Prefer diagrams for configuration and failure flows. Every outcome must identify its configuration; preset labels distinguish supported choices from settings actually selected by the user. Keep the README consistency summary short and walkthroughs in the detailed guide.

## Implementation scope constraint

Use Redis Enterprise native features and existing client facilities for conflict semantics, persistence/durability, expiry, capacity/eviction, pooling, and timeouts. Most remaining baseline decisions are configuration or capability verification, not new functionality. Limit custom baseline code to the selected read/write adapter behavior and its necessary validation, deadlines, cleanup, and identity handling. Do not add replacement database features or dynamic group, clock-correction, resource-management, or service-level enforcement subsystems. Monotonic and Linearizable remain deferred custom extensions, not implied native capabilities.

## Client foundation decision — 2026-11-10

Direct user instruction requires the adapter to **build on top of, or work with, the [official Redis clients](https://redis.io/docs/latest/develop/clients/)**. This broadens the preceding Jedis/redis-py selection: **Jedis for Java** and **redis-py for Python** remain initial integration targets, with other official clients allowed through the same adapter contract. The Redis client index was checked on 2026-11-10 and lists both clients as supported. Exact dependency versions, language-specific API/packaging, resource ownership, and integration validation remain open. Support for additional clients must be validated before being claimed. The legacy Python spike does not establish production API compliance.

## Open decisions before implementation

Assign the responsible owners; no names or approvals are inferred.

1. **Platform configuration:** record the deployed Redis/database build, selected official-client versions (initially Jedis/redis-py), supported commands/data types, replica layout, native persistence/eviction and shard capacity, and deployment-configured targets/epochs. Use the platform and client facilities as provided.
2. **Read adapter integration:** define official-client integration through public APIs, initially Java/Jedis and Python/redis-py, including supplied-client/pool ownership and native candidate-storage commands; document native conflict behavior. Configure allowed groups/overrides including local, implement the selected concurrent read race/shared deadline/cleanup, and reuse existing client pools and limits. No custom conflict engine or dynamic group-management feature. Caller write-context and lineage enforcement are not baseline requirements.
3. **Distribution:** select acknowledgment rules, bounded request-time fan-out scheduling/retries, idempotency/conflict handling, and target readiness. No application background repair or historical-backfill feature is selected.
4. **Deployment and measurement:** configure native expiration, persistence, retention and capacity plus client request/pool limits. Document clock/expiry and durability limitations, measure latency/throughput and failure outcomes, and record operational responsibilities. Do not build clock correction or a service-level enforcement subsystem; authorization/revocation policy remains the application's responsibility.
5. **Stronger read contracts:** define monotonic-modifier floor storage/transport and on/off/Local/Available transitions, concurrency/rollback protection, trustworthy state-history comparison, deletion/absence/expiry/generation handling, and bounded failure semantics on both backends; define/prove each linearizable commit/read/failure protocol. Native causal configuration needs no separate application Causal read option.
6. **Delivery:** choose CI/provisioning, artifact reviewers, production release authority, and rollout/rollback checks.

For each resolved decision, record artifact revision, reviewer, date, rationale, and review/commit link. Document generation and PR submission do not constitute technical or production acceptance.

## AWS spike implementation

The user requested a real AWS spike using Terraform, selected AWS profile 735486936198_SuperUserAccess, supplied a Redis license, explicitly authorized its storage in an AWS Secrets Manager destination, and requested the latest Redis Enterprise/Software version. The official download selector and release notes identified 8.2.6-25; the spike pins that installer and requests database version 8.8. Secret values are not repository artifacts. See spike/README.md for the experimental implementation, topology, cost basis, and limitations. The historical spike does not override the current production delivery-recovery scope; its recorded presets/control names retain their original meanings.

Local and Available inherit same-key causal operation ordering when Active-Active causal consistency is enabled. This backend ordering does not ensure a region has caught up or prevent a caller from reading older state after switching regions. With monotonic on, both strategies additionally enforce per-caller same-key non-regression using automatic read history; independent clusters need that enforcement too. Neither causal ordering nor monotonic reads guarantees the latest completed write. Same-key Redis ordering must not be assumed to order multiple snapshot/hint keys.
