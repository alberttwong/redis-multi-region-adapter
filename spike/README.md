# AWS session latency spike

This is an **experimental measurement harness**, not the production session SDK or a strict geographic-consistency implementation. It deploys Redis Software **8.2.6-25**, the latest release verified on 2026-11-09, and requests database compatibility **8.8**. The [official download selector](https://redis.io/downloads/#Redis_Software) and [release notes](https://redis.io/docs/latest/operate/rs/release-notes/rs-8-2-releases/rs-8-2-6-25/) identify that build. The installer checksum is pinned in deployment variables; do not use a floating latest image for results.

The revised production API has `local` (one regional lookup) and default `available` (concurrently race all selected group members, including local; first non-null value, or null on all-null/deadline). Session reads have been removed from production scope. This legacy spike retains `latest`, `any`, and `required` controls and explicitly managed actor context; **it does not implement the new group-racing Available policy**. Historical run reports and runtime controls retain their original meanings. New production reads need separate implementation and measurement.

## Topology

Terraform creates five isolated VPCs, a full mesh of ten inter-region peering links, private DNS, fifteen Redis nodes (three per regional cluster across AZs), and five regional runners. Each regional database uses three primary data shards plus replicas. The independent and Active-Active datasets coexist on ports 12000 and 12001 so they can use the same hardware; run one workload at a time and record residual background traffic.

US: A1/A2 in us-west-2, B1 in us-east-1, C1 in us-east-2. EU: D1 in eu-west-1, E1 in eu-central-1. A1/A2 are separate actors on one west runner with separate context; no context crosses clients. Cross-region replication/fan-out carries data, not caller context. Explicit group metadata does not narrow the all-target barrier in this spike.

No SSH or public Redis ingress is configured. Instances have public IPv4 for outbound package/SSM access; data/API ingress is limited to the five private VPC CIDRs, with Redis-internal traffic restricted to its regional security group. Access uses SSM, IMDSv2, separate node/runner roles, encrypted EBS and S3, and AWS Secrets Manager. Runner roles cannot read the license or admin secret.

The initial data-path baseline uses Redis authentication on private peered addresses **without client TLS**. Record `data_tls=false` in every result and do not compare it to TLS-enabled production service levels. Admin bootstrap uses loopback HTTPS with the locally served certificate pinned for that session. TLS, failure recovery, and final production context security need separate validation.

## Prerequisites and cost

Use an isolated AWS account or approved namespace and a valid AWS profile. Terraform requires an explicit account ID. Supply three secret ARNs only: the supplied license, generated admin credentials (`username`, `password` JSON), and generated database credentials (`password` JSON). No secret values belong in tfvars, Terraform state, user data, code archives, or results.

The selected account's AWS Price List API quoted **$3.5032/hour compute** on 2026-11-09 for 15 m6i.xlarge nodes plus five c6i.large runners across the five regions. This excludes EBS, twenty public IPv4 addresses, inter-region data transfer, DNS, S3, Secrets Manager, and licensing. Prices can change. ExpiresAt is a tag, **not an automatic teardown**. Destroy the isolated deployment after collecting results; preserve reports first. The license and generated credential secrets are external to Terraform and need a separate retention/deletion decision.

## Reproduce deployment

```bash
python3 -m venv spike/.venv
spike/.venv/bin/pip install -r spike/requirements.txt
PYTHONPATH=spike spike/.venv/bin/python -m unittest discover -s spike/tests -v
terraform -chdir=spike/infra init
terraform -chdir=spike/infra fmt -check -recursive
terraform -chdir=spike/infra validate
```

Copy `infra/terraform.tfvars.example` to ignored `infra/terraform.tfvars.json` (JSON syntax) or `infra/terraform.tfvars` (HCL syntax), replacing placeholders with ARNs and a checksum. Do not copy a raw license. The official Ubuntu 22.04 AMD64 package used here is:

```text
https://redis-enterprise-software-downloads.s3.amazonaws.com/8.2.6/redislabs-8.2.6-25-jammy-amd64.tar
SHA256 27dad5afff38d98da3db869023394ba74f746a127eaf20cf50910949a4903118
```

This checksum records the downloaded vendor HTTPS artifact, not a separately obtained vendor signature. Provider selections are pinned in `.terraform.lock.hcl`; Redis nodes use Ubuntu 22.04; runners use Ubuntu 24.04 with Python 3.12. Bootstrap disables the Ubuntu DNS stub listener to free port 53 for Redis Software. Ubuntu AMI IDs resolved during the plan are recorded in inventory.

```bash
terraform -chdir=spike/infra plan -out=spike.tfplan
terraform -chdir=spike/infra apply spike.tfplan
mkdir -p spike/local
terraform -chdir=spike/infra output -json inventory > spike/local/inventory.json
spike/.venv/bin/python spike/scripts/control.py --inventory spike/local/inventory.json upload
spike/.venv/bin/python spike/scripts/control.py --inventory spike/local/inventory.json ready
```

`ready` checks node installer completion and runner Python/dependencies, not cluster/database readiness. Wait for cloud-init/SSM completion before proceeding. The default control profile is the selected profile; use `--profile` to override it.

```bash
spike/.venv/bin/python spike/scripts/control.py --inventory spike/local/inventory.json create
spike/.venv/bin/python spike/scripts/control.py --inventory spike/local/inventory.json join
spike/.venv/bin/python spike/scripts/control.py --inventory spike/local/inventory.json database
spike/.venv/bin/python spike/scripts/control.py --inventory spike/local/inventory.json active-active
spike/.venv/bin/python spike/scripts/control.py --inventory spike/local/inventory.json inspect
```

Create/join are first-time actions, not a production idempotent cluster reconciler. Use inspect and SSM command IDs to diagnose failures before repeating them. Inspect emits only non-secret database configuration fields. Confirm version, active state, three primary shards, replication, AOF policy, and endpoint reachability before comparing presets. Three-shard setup follows the [database API](https://redis.io/docs/latest/operate/rs/references/rest-api/objects/bdb/); native replication setup follows [crdb-cli create](https://redis.io/docs/latest/operate/rs/references/cli-utilities/crdb-cli/crdb/create/).

## Run scenarios

Start at low load, then vary scheduled rate, payload size, write ratio, policy, and deadlines. Run A, B, C, D, and E sequentially, with a distinct run ID for every comparison. Native A writes once. Independent B/D use current-write fan-out. C/E atomically capture a slot-local Redis Stream obligation and start a separate replay process on each origin runner. AOF-always plus configured replicas is the selected persistence policy, not a proof against every failure. The replay process is bounded to the run duration plus 120 seconds. The controller normally terminates it after the workload and a three-second drain interval, then uploads delivery counters. Its continued operation is required for recovery, and no production supervisor is implemented.

```bash
spike/.venv/bin/python spike/scripts/control.py --inventory spike/local/inventory.json \
  --preset B --run-id b-latest-1k-lowload --duration 60 --rate 10 \
  --payload-bytes 1024 --policy latest run
```

Results go to the private bucket under `results/<run-id>/`. Collect JSONL samples and summary JSON to ignored `spike/results/`:

```bash
spike/.venv/bin/python spike/scripts/collect.py --inventory spike/local/inventory.json --run-id b-latest-1k-lowload
```

The workload uses a common synthetic session keyspace across clients; each actor retains only its own contexts. Writes are serialized per actor in this first spike. This is a six-actor latency experiment, not a throughput-capacity benchmark. Rate is scheduled per regional runner; A1/A2 split the west rate. Bounded actor queues record overload rather than silently reducing the requested offered load. Increase rate carefully and distinguish scheduling lag from service time.

`latest` reads with no own context return local discovery state. `required` without own context records context-required errors; use enough warmup/writes or an explicitly seeded protected probe when studying that path. Unknown writers' updates never become another actor's freshness token. The prototype discovery hint keeps the greatest sequence within a writer lineage and uses local arrival order between independent lineages; it does not implement a globally ordered session revision.

## Interpreting results

The [2026-11-09 AWS baseline](reports/aws-baseline-20261109.md) contains actual measurements and a sanitized deployment manifest. All twenty EC2 instances were verified stopped afterward; EBS, artifacts, secrets, and Terraform state are retained.

JSONL rows record actor, region, operation, policy, protected/unprotected condition, outcome, response time from scheduled arrival, service time, and scheduling lag. They exclude payloads, credential-bearing URLs, session IDs, raw contexts, and exception messages. Summaries show nearest-rank p50/p95/p99/max for all attempts and each outcome, alongside outcome rates. Fewer than 10,000 samples per group carries a tail-sample warning; that is a caution, not a confidence-interval calculation. Never average regional p99s.

Polling and origin capture are real measured prototype code, but the production SDK's authenticated context encoding, multi-process sequencing, merge semantics, connection balancing, and comprehensive crash recovery are not implemented. Cross-client data visibility can differ from command latency; do not call a fast stale/null response fresh. No benchmark result is a strict consistency proof.

See [latency.md](../latency.md) for the model and the differences between client-local reads, residual freshness waits, and transport observation. Report the exact run configuration, sample counts, missing/timeout/error rates, and measurement limitations with every p99.

## Stop or teardown

To preserve this isolated spike while ending compute charges, stop its twenty inventory instances:

```bash
spike/.venv/bin/python spike/scripts/power.py --inventory spike/local/inventory.json stop
# Later, restart; allow Redis/SSM to recover and inspect databases before another run.
spike/.venv/bin/python spike/scripts/power.py --inventory spike/local/inventory.json start
```

Stopping retains EBS volumes and infrastructure, so storage and other retained-service charges continue. Redis-reported recovery and endpoint health must be verified before treating a restarted deployment as ready.


Download results and record inventory first. Empty only this deployment's generated artifact bucket after preserving reports, then run `terraform -chdir=spike/infra destroy`. The bucket intentionally has `force_destroy=false` to prevent accidental report loss. Confirm no tagged EC2 instances remain running. Secrets created outside Terraform are not deleted by destroy. Never run cleanup against unrelated resources or a different account.
