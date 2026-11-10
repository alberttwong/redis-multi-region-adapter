# Multi-region read behavior

Design documents plus an experimental AWS latency spike. Start with README.md, spec.md, plan.md, and spike/README.md. The legacy spike is not the revised production SDK or a linearizable protocol.

## Spike commands

- Setup: `python3 -m venv spike/.venv` then `spike/.venv/bin/pip install -r spike/requirements.lock.txt`.
- Tests: `PYTHONPATH=spike spike/.venv/bin/python -m unittest discover -s spike/tests -v`.
- Terraform: `terraform -chdir=spike/infra fmt -check -recursive` and `terraform -chdir=spike/infra validate`.
- Deployment/run commands: spike/README.md. Existing AWS authorization is not a request to provision or restart infrastructure during documentation work.
- Keep state, plans, inventory/results, raw license, and credentials outside Git.

## Required behavior

- Default `available`: query all selected group members concurrently, including local. Return the first valid non-null value; null on all-null completion or shared deadline without a value. An early null never beats a pending value.
- Explicit `local`: query only local; valid value or null, with infrastructure errors separate. Active-Active handles propagation, or independent mode uses adapter write fan-out.
- Session reads have been removed from production scope. No caller write context, RYOW enforcement, successor proof, public exact-version selector, or `greedy` policy. Proposed `coordinated` and deferred `linearizable` are unsupported.
- Available can return stale data; timeout-null is not proof of absence. Capture/validate groups including local; no silent target removal, sequential fallback, latest comparison, or write-back.
- Cancel or discard losing/late results; bound concurrency, pools, deadlines, and request sizes. Validate authorization, key binding, generation, integrity, and expiry.
- US: west/east-1/east-2; EU: eu-west-1/eu-central-1. A1/A2 share the west database; six clients mean five targets, fifteen primary shards before replicas. Read groups do not shrink all-target write obligations.
- Independent request-only refreshes the next same-session update's current version. Optional durable replay captures obligations before success. Local acknowledgment is baseline; independent all-target verifies placement, not ordering/durability.
- Project backend rules: `linearizable` requires Active-Active plus a validated coordination overlay; Active-Active alone is eventually consistent. Proposed `coordinated` targets independent, non-Active-Active clusters; its linearizable-like freshness/order/failure contract is undefined. Reject both unimplemented policies and backend mismatches; claim no Coordinated freshness guarantee.
- Preserve IDs on uncertain-write reconciliation. Internal placement misses may be described as **snapshot missing**; public Available misses/timeouts return null.
- Never log payloads, credentials, bearer IDs, or raw tokens.

## Completion evidence

Use validation.md and REVIEW.md. Production scenarios are proposed acceptance checks, not executed results. Legacy spike tests and measurements do not certify group-racing Available behavior. Keep plans and documentation synchronized with actual implementation.
