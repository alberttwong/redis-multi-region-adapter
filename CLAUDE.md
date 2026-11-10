# Multi-region read behavior

Design documents plus an experimental AWS latency spike. Start with README.md, spec.md, plan.md, and spike/README.md. The legacy spike is not the revised production SDK or a linearizable protocol.

## Spike commands

- Setup: `python3 -m venv spike/.venv` then `spike/.venv/bin/pip install -r spike/requirements.lock.txt`.
- Tests: `PYTHONPATH=spike spike/.venv/bin/python -m unittest discover -s spike/tests -v`.
- Terraform: `terraform -chdir=spike/infra fmt -check -recursive` and `terraform -chdir=spike/infra validate`.
- Deployment/run commands: spike/README.md. Existing AWS authorization is not a request to provision or restart infrastructure during documentation work.
- Keep state, plans, inventory/results, raw license, and credentials outside Git.

## Required behavior

- Build on top of, or work with, the official Redis clients (https://redis.io/docs/latest/develop/clients/), initially Jedis for Java and redis-py for Python. Preserve the same contract across supported integrations; pin and validate production dependency versions. Reuse public client APIs and respect caller ownership of supplied clients/pools. Prefer Redis Enterprise native capabilities and the selected clients' facilities. Configure/document native conflict semantics, persistence/durability, expiration, eviction/capacity, pools, and timeouts; do not implement replacements. Custom baseline code is limited to selected read/write fan-out, optional all-target verification, and necessary validation, bounded execution, cleanup, and identity handling. Keep groups deployment-configured. Do not add custom clock correction, group/resource management, or service-level enforcement. Monotonic/Linearizable remain deferred extensions outside baseline implementation.

- Default `available` with `monotonic: false`: query all selected group members concurrently, including local. Return the first valid non-null value; null on all-null completion or shared deadline without a value. An early null never beats a pending value.
- Explicit `local`: query only local; valid value or null, with infrastructure errors separate. Active-Active handles propagation, or independent mode uses adapter write fan-out.
- Session reads have been removed from production scope. No caller write-context/RYOW policy, public exact-version selector, or `greedy` policy. Proposed Monotonic does require accepted read-history proofs. Proposed `monotonic: true` on Local/Available and the `linearizable`/`linearizable-coordinated` policies need validated adapter/protocol integration before use.
- Available can return stale data; timeout-null is not proof of absence. Capture/validate groups including local; no silent target removal, sequential fallback, latest comparison, or write-back.
- Cancel or discard losing/late results; bound concurrency, pools, deadlines, and request sizes. Validate authorization, key binding, generation, integrity, and expiry.
- US: west/east-1/east-2; EU: eu-west-1/eu-central-1. A1/A2 share the west database; six clients mean five targets, fifteen primary shards before replicas. Read groups do not shrink all-target write obligations.
- Delivery recovery follows the backend: independent clusters have no background repair; Active-Active is Redis-managed. No recovery selector, outbox capture, or replay worker belongs to the production baseline. Each independent same-session write fans out its current version. Local acknowledgment is baseline; all-target verifies placement, not ordering/durability. Preserve historical spike replay controls and reports.
- Monotonic is a proposed boolean modifier (default false) on Local/Available on either backend, never a standalone policy: automatically retain/transport each caller's last successful tracked read floor, accept same/proven later state, never regress it, and wait/fail rather than return older/unproven state or timeout-null when an unexpired floor exists. Local must remain local-only; Available filters its group race. No latest-write or RYOW guarantee; no manual version input. Off-reads do not roll back the retained floor; sequential linearizable reads already imply monotonicity. Concurrency, absence/deletion/expiry, and history evidence need a protocol.
- Causal is removed from read/write option tables and custom implementation scope. Redis's optional Active-Active causal flag remains backend configuration; it does not establish a caller's read floor or linearizability.
- Both Linearizable variants use **slow++** planning ratings for reads and writes and target identical real-time per-key guarantees through custom protocols. Ratings are not measured SLOs. Reject all unimplemented/removed policies and backend mismatches; no inherent speed ranking is established.
- Preserve IDs on uncertain-write reconciliation. Internal placement misses may be described as **snapshot missing**; public Available misses/timeouts return null.
- Never log payloads, credentials, bearer IDs, or raw tokens.

## Completion evidence

Use validation.md and REVIEW.md. Production scenarios are proposed acceptance checks, not executed results. Legacy spike tests and measurements do not certify group-racing Available behavior. Keep plans and documentation synchronized with actual implementation.
