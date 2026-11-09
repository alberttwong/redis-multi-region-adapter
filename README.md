# Multi-region session consistency

Design artifacts for **read-your-own-writes (RYOW)** on **Redis Software 8.x, with three primary data shards per regional database**. Choose Active-Active or independent regional databases with adapter-managed fan-out. Replica shards are additional; confirm that sizing interpretation before provisioning.

A caller that carries the context from an acknowledged write must be able to read that state after moving regions. The default is latest known locally while honoring the caller’s last acknowledged write. The adapter returns an eligible local snapshot, retrieves/waits for the required snapshot, or returns an explicit freshness error. It never reports success with older state or an ordinary propagation-related miss.

Device B defaults to **latest local + RYOW**, and can explicitly choose **required version** (exactly 42, wait/error) or **any version** (local available state, possibly older, or `null`). Required reads need authenticated version context transferred to Device B. Any-version reads are explicit eventual reads; they never silently replace a required read.

## Documents

| File | Purpose |
| --- | --- |
| [decisions.md](decisions.md) | Configuration, recovery, version 42, and read-policy diagrams |
| [backends.md](backends.md) | Active-Active versus independent databases, fan-out, and acknowledgment policies |
| [consistency.md](consistency.md) | Consistency levels, default policy, and Device A/B examples |
| [intent.md](intent.md) | Desired outcome and boundaries |
| [spec.md](spec.md) | RYOW contract, context propagation, and adapter design |
| [plan.md](plan.md) | Proposed implementation sequence and proof |
| [validation.md](validation.md) | Acceptance scenarios |
| [operations.md](operations.md) | Recovery, rollout, and observability |
| [REVIEW.md](REVIEW.md) | Review priorities |
| [CLAUDE.md](CLAUDE.md) | Repository instructions |
| [sources.md](sources.md) | Source precedence and decisions |

## Selected scope

Active-Active mode uses Redis-managed replication. Independent mode uses adapter-managed fan-out with optional durable replay; it may optionally wait for all target copies. The adapter supplies caller context, exact-snapshot validation, and bounded freshness waits. No home cluster, geographic write barrier, or strict commit authority is required for this phase. Other callers' updates and immediate global revocation are outside the RYOW guarantee.

The proposal uses immutable snapshots and a caller-carried snapshot identity, avoiding a global revision counter. Application middleware carries this context; business code does not poll Redis or compare versions. Without context, exact-ID lookup remains eventual and cannot claim cross-region RYOW.

## Agreed Device A/B behavior

A writes 42 in Region A, then reads with context: return 42 or a proven successor. B reads Region B without that context: local 41 or `null` is allowed until propagation arrives. B with transferred context waits for the required state or gets a freshness error. Strict geographic would prohibit B's stale success even without context, for reads beginning after A's completed write within the group. See [consistency.md](consistency.md).

## Status

Updated 2026-11-09: the repository owner selected RYOW. Detailed design, tooling, retention, durability, and service levels remain drafts. This repository contains documentation only; no SDK, tests, infrastructure, or enforcement hooks have been implemented.

The artifact structure follows the [AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook). Repository Markdown is the proposed design source of truth; the source deck is provenance.
