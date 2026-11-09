# Sources and decisions

Updated: 2026-11-09. Authored documents omit customer identities and workload branding. This file records provenance and decision status; [spec.md](spec.md) owns behavior.

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

No exact-build support matrix, deployed configuration, vendor approval of a strict protocol, or measured service levels have been obtained. Snapshot/context schemas, fan-out, and workers are proposed application design.

## Selected decisions

All user decisions below were made on 2026-11-09. They select scope, not every proposed implementation mechanism.

- Redis Software 8.x, with Active-Active and an additional non-Active-Active option. The independent regional fan-out architecture is the proposed implementation of that additional option.
- Three shards; interpreting this as three primary shards per regional database, with replicas additional, remains a sizing assumption to confirm.
- Default **latest locally known while honoring the caller's last write (RYOW)**. Explicit exact-version and any-version reads remain available. Strict geographic/global consistency is deferred.
- A reads/writes in `us-west-2`; independent B reads/writes in `us-east-1`. This does not change policy defaults. Both retain context from their own writes. They have no direct or out-of-band application communication: no token/context handoff, revision notification, or shared latest-version directory. A’s context protects A’s own reads; B uses locally available Redis state and cannot know an unpropagated A write exists. Redis replication/adapter fan-out still transports data.
- Durable replay is optional. Independent acknowledgment and recovery are separate choices; no particular recovery combination is selected. Local acknowledgment remains the baseline, with all-target verification an explicit option.
- Request-only mode distributes only the latest version on the next same-session insert/update, rather than requiring manual repair as its normal flow. No complete snapshot or historical resend is required. It need not fill historical gaps. Describe an absent expected exact snapshot as **snapshot missing**.
- Prefer diagrams for configuration and failure flows. Every outcome must identify its configuration; preset labels distinguish supported choices from settings actually selected by the user. Keep the README consistency summary short and walkthroughs in the detailed guide.

## Open decisions before implementation

Assign the responsible owners; no names or approvals are inferred.

1. **Platform:** pin product/database/client builds, supported commands per mode, replica layout, persistence/eviction, shard capacity, target discovery, and authoritative configuration-epoch storage.
2. **Context and lineage:** choose language/framework, token transport and binding, write serialization across app instances, response-order protection, same-caller continuity across requests/regions, provenance/sequence evidence, and candidate selection for incomparable lineages. A signed token alone does not solve branching writes.
3. **Distribution:** select supported acknowledgment/recovery combinations, capture/worker technology when replay is enabled, slot-scoped outbox discovery across three shards, idempotency/conflict handling, target readiness, and replay/catch-up retention.
4. **Service and security:** agree payload/token limits, latency/throughput targets, deadlines, expiry/skew, context/record lifetime, RPO/RTO, revocation/authorization responsibilities, and incident ownership.
5. **Delivery:** choose CI/provisioning, artifact reviewers, production release authority, and rollout/rollback checks.

For each resolved decision, record artifact revision, reviewer, date, rationale, and review/commit link. Document generation and PR submission do not constitute technical or production acceptance.
