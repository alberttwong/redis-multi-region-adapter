# AWS latency baseline — 2026-11-09

Measured foreground outcomes: null=135, success=7365. Warmup operations are excluded.

These are live five-region AWS measurements of the experimental adapter. They are descriptive samples, not a production SLO or proof of strict geographic consistency. Every group below has fewer than 10,000 samples; p99 is particularly sensitive to individual observations.

A = native Active-Active/local acknowledgment; B = independent/request-only/local; C = independent/replay/local; D = independent/request-only/all five targets; E = independent/replay/all five targets. All use default `latest`: locally selected state with each caller’s own RYOW context. Independent clients do not receive another writer’s context.

## Configuration

Redis Software 8.2.6-25; Redis database 8.8; three primary shards plus replication per database and region; AOF `appendfsync-always`; 15 m6i.xlarge Redis nodes and five c6i.large runners. Both database types share the same hardware; presets ran sequentially. Private peered data paths use authentication without client TLS. Six serialized actors exercise 32 shared synthetic sessions, 1 KiB payload, 20% writes, 10-second warmup and 60-second measurement, with five scheduled operations/second per regional runner (west split between A1/A2). These are low-load latency probes, not capacity tests.

Latencies include scheduling delay, adapter work, connection pool, Redis, and network. All-target writes verify the immutable copy at all four remote targets with a GET after delivery. This deliberately costs an additional phase; it is an adapter placement barrier, not a consensus commit. Protected reads may fall back to their exact own-write version when the local discovery candidate has incomparable lineage. Null unprotected reads are reported explicitly. Because each actor serializes reads and writes, a long WAN write delays later scheduled reads: D/E read response tails can include client head-of-line blocking. Service p99 separates actual operation time from that generator queue; a concurrent-request production model requires a separate run.

## Regional p99 ranges

Each range spans the five individual regional p99s; it is not a pooled percentile. Service time excludes generator scheduling delay. Counts and outcomes below remain the authoritative detail.

| Preset | Read response p99 range ms | Write response p99 range ms | Write service p99 range ms |
| --- | ---: | ---: | ---: |
| A | 2.51–4.03 | 2.70–4.25 | 1.54–3.99 |
| B | 1.78–2.76 | 1.75–2.62 | 0.63–0.85 |
| C | 1.86–2.38 | 1.86–3.22 | 0.70–2.01 |
| D | 1.89–260.26 | 184.08–631.45 | 182.99–289.28 |
| E | 1.88–171.89 | 188.96–456.03 | 187.67–287.89 |

## Samples by path

| Preset | Origin | Path | n | p50 ms | p95 ms | p99 ms | Service p99 ms | Outcomes |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| A | eu-central-1 | read protected | 159 | 3.19 | 3.89 | 4.01 | 2.88 | success=159 (100.0%) |
| A | eu-central-1 | read unprotected | 78 | 2.20 | 2.63 | 2.71 | 1.60 | null=12 (15.4%), success=66 (84.6%) |
| A | eu-central-1 | write  | 63 | 3.56 | 3.97 | 4.24 | 3.09 | success=63 (100.0%) |
| A | eu-west-1 | read protected | 167 | 1.82 | 2.43 | 2.53 | 1.33 | success=167 (100.0%) |
| A | eu-west-1 | read unprotected | 69 | 1.52 | 1.90 | 1.95 | 0.84 | null=7 (10.1%), success=62 (89.9%) |
| A | eu-west-1 | write  | 64 | 2.19 | 2.57 | 2.70 | 1.54 | success=64 (100.0%) |
| A | us-east-1 | read protected | 153 | 2.61 | 3.35 | 3.45 | 2.33 | success=153 (100.0%) |
| A | us-east-1 | read unprotected | 71 | 1.96 | 2.37 | 2.48 | 1.49 | null=7 (9.9%), success=64 (90.1%) |
| A | us-east-1 | write  | 76 | 3.07 | 3.51 | 3.54 | 3.05 | success=76 (100.0%) |
| A | us-east-2 | read protected | 147 | 3.03 | 3.67 | 3.90 | 2.78 | success=147 (100.0%) |
| A | us-east-2 | read unprotected | 102 | 2.06 | 2.55 | 2.65 | 1.61 | null=10 (9.8%), success=92 (90.2%) |
| A | us-east-2 | write  | 51 | 3.28 | 3.82 | 3.94 | 2.95 | success=51 (100.0%) |
| A | us-west-2 | read protected | 95 | 3.44 | 4.00 | 4.21 | 2.95 | success=95 (100.0%) |
| A | us-west-2 | read unprotected | 151 | 2.20 | 2.69 | 2.82 | 1.61 | null=9 (6.0%), success=142 (94.0%) |
| A | us-west-2 | write  | 54 | 3.66 | 4.16 | 4.25 | 3.99 | success=54 (100.0%) |
| B | eu-central-1 | read protected | 177 | 1.60 | 2.43 | 2.76 | 1.01 | success=177 (100.0%) |
| B | eu-central-1 | read unprotected | 71 | 1.43 | 1.88 | 2.57 | 0.65 | null=5 (7.0%), success=66 (93.0%) |
| B | eu-central-1 | write  | 52 | 1.62 | 2.52 | 2.62 | 0.83 | success=52 (100.0%) |
| B | eu-west-1 | read protected | 176 | 1.29 | 1.79 | 1.87 | 0.74 | success=176 (100.0%) |
| B | eu-west-1 | read unprotected | 54 | 1.07 | 1.65 | 1.70 | 0.51 | null=7 (13.0%), success=47 (87.0%) |
| B | eu-west-1 | write  | 70 | 1.37 | 1.79 | 1.86 | 0.73 | success=70 (100.0%) |
| B | us-east-1 | read protected | 143 | 1.23 | 1.71 | 1.79 | 0.67 | success=143 (100.0%) |
| B | us-east-1 | read unprotected | 94 | 1.09 | 1.61 | 1.71 | 0.51 | null=9 (9.6%), success=85 (90.4%) |
| B | us-east-1 | write  | 63 | 1.21 | 1.70 | 1.75 | 0.63 | success=63 (100.0%) |
| B | us-east-2 | read protected | 186 | 1.24 | 1.80 | 1.89 | 0.77 | success=186 (100.0%) |
| B | us-east-2 | read unprotected | 62 | 1.14 | 1.59 | 1.61 | 0.46 | null=10 (16.1%), success=52 (83.9%) |
| B | us-east-2 | write  | 52 | 1.38 | 1.82 | 1.85 | 0.72 | success=52 (100.0%) |
| B | us-west-2 | read protected | 91 | 1.62 | 2.20 | 2.28 | 1.21 | success=91 (100.0%) |
| B | us-west-2 | read unprotected | 155 | 1.33 | 1.76 | 1.87 | 0.67 | null=7 (4.5%), success=148 (95.5%) |
| B | us-west-2 | write  | 54 | 1.54 | 1.97 | 2.07 | 0.85 | success=54 (100.0%) |
| C | eu-central-1 | read protected | 160 | 1.66 | 2.20 | 2.32 | 1.14 | success=160 (100.0%) |
| C | eu-central-1 | read unprotected | 67 | 1.29 | 1.84 | 2.93 | 2.27 | success=67 (100.0%) |
| C | eu-central-1 | write  | 73 | 1.51 | 2.01 | 2.07 | 0.91 | success=73 (100.0%) |
| C | eu-west-1 | read protected | 175 | 1.41 | 2.02 | 2.36 | 1.72 | success=175 (100.0%) |
| C | eu-west-1 | read unprotected | 67 | 1.29 | 1.68 | 1.71 | 0.53 | null=1 (1.5%), success=66 (98.5%) |
| C | eu-west-1 | write  | 58 | 1.33 | 1.90 | 3.22 | 2.01 | success=58 (100.0%) |
| C | us-east-1 | read protected | 199 | 1.29 | 1.81 | 1.86 | 0.72 | success=199 (100.0%) |
| C | us-east-1 | read unprotected | 37 | 1.18 | 1.65 | 1.69 | 0.44 | null=1 (2.7%), success=36 (97.3%) |
| C | us-east-1 | write  | 64 | 1.41 | 1.75 | 1.86 | 0.70 | success=64 (100.0%) |
| C | us-east-2 | read protected | 160 | 1.37 | 1.82 | 1.89 | 0.75 | success=160 (100.0%) |
| C | us-east-2 | read unprotected | 80 | 1.25 | 1.69 | 1.75 | 0.49 | success=80 (100.0%) |
| C | us-east-2 | write  | 60 | 1.41 | 1.80 | 1.88 | 0.72 | success=60 (100.0%) |
| C | us-west-2 | read protected | 101 | 1.72 | 2.28 | 2.39 | 1.15 | success=101 (100.0%) |
| C | us-west-2 | read unprotected | 138 | 1.49 | 1.90 | 2.01 | 0.75 | null=1 (0.7%), success=137 (99.3%) |
| C | us-west-2 | write  | 61 | 1.63 | 1.97 | 2.11 | 0.90 | success=61 (100.0%) |
| D | eu-central-1 | read protected | 173 | 1.70 | 173.93 | 319.35 | 1.03 | success=173 (100.0%) |
| D | eu-central-1 | read unprotected | 55 | 1.53 | 146.96 | 259.74 | 1.49 | null=1 (1.8%), success=54 (98.2%) |
| D | eu-central-1 | write  | 72 | 287.23 | 459.74 | 631.45 | 286.46 | success=72 (100.0%) |
| D | eu-west-1 | read protected | 161 | 1.38 | 38.76 | 75.59 | 0.80 | success=161 (100.0%) |
| D | eu-west-1 | read unprotected | 92 | 1.37 | 38.71 | 112.64 | 0.61 | null=3 (3.3%), success=89 (96.7%) |
| D | eu-west-1 | write  | 47 | 238.11 | 275.23 | 312.23 | 237.41 | success=47 (100.0%) |
| D | us-east-1 | read protected | 161 | 1.30 | 1.78 | 1.89 | 0.74 | success=161 (100.0%) |
| D | us-east-1 | read unprotected | 82 | 1.15 | 1.61 | 1.66 | 0.52 | null=3 (3.7%), success=79 (96.3%) |
| D | us-east-1 | write  | 57 | 183.58 | 184.03 | 184.08 | 182.99 | success=57 (100.0%) |
| D | us-east-2 | read protected | 156 | 1.25 | 1.86 | 2.04 | 1.37 | success=156 (100.0%) |
| D | us-east-2 | read unprotected | 87 | 1.12 | 1.64 | 2.46 | 1.85 | null=2 (2.3%), success=85 (97.7%) |
| D | us-east-2 | write  | 57 | 197.32 | 197.77 | 197.86 | 196.73 | success=57 (100.0%) |
| D | us-west-2 | read protected | 97 | 1.67 | 2.18 | 2.23 | 1.17 | success=97 (100.0%) |
| D | us-west-2 | read unprotected | 151 | 1.29 | 1.74 | 1.86 | 0.71 | null=3 (2.0%), success=148 (98.0%) |
| D | us-west-2 | write  | 52 | 287.66 | 289.26 | 290.07 | 289.28 | success=52 (100.0%) |
| E | eu-central-1 | read protected | 182 | 1.82 | 87.12 | 172.06 | 1.17 | success=182 (100.0%) |
| E | eu-central-1 | read unprotected | 64 | 1.55 | 86.91 | 171.46 | 0.67 | null=6 (9.4%), success=58 (90.6%) |
| E | eu-central-1 | write  | 54 | 286.04 | 371.06 | 456.03 | 285.29 | success=54 (100.0%) |
| E | eu-west-1 | read protected | 156 | 1.62 | 69.76 | 70.89 | 0.81 | success=156 (100.0%) |
| E | eu-west-1 | read unprotected | 76 | 1.30 | 36.15 | 70.10 | 0.54 | null=9 (11.8%), success=67 (88.2%) |
| E | eu-west-1 | write  | 68 | 235.38 | 270.30 | 339.39 | 234.74 | success=68 (100.0%) |
| E | us-east-1 | read protected | 162 | 1.34 | 1.82 | 1.93 | 0.73 | success=162 (100.0%) |
| E | us-east-1 | read unprotected | 78 | 1.20 | 1.67 | 1.72 | 0.48 | null=8 (10.3%), success=70 (89.7%) |
| E | us-east-1 | write  | 60 | 186.36 | 186.88 | 188.96 | 187.67 | success=60 (100.0%) |
| E | us-east-2 | read protected | 163 | 1.32 | 1.83 | 1.88 | 0.75 | success=163 (100.0%) |
| E | us-east-2 | read unprotected | 88 | 1.13 | 1.62 | 2.03 | 0.68 | null=3 (3.4%), success=85 (96.6%) |
| E | us-east-2 | write  | 49 | 195.27 | 195.82 | 196.02 | 194.85 | success=49 (100.0%) |
| E | us-west-2 | read protected | 114 | 1.63 | 2.28 | 2.36 | 1.18 | success=114 (100.0%) |
| E | us-west-2 | read unprotected | 121 | 1.36 | 1.84 | 1.91 | 0.72 | null=11 (9.1%), success=110 (90.9%) |
| E | us-west-2 | write  | 65 | 285.57 | 288.63 | 288.76 | 287.89 | success=65 (100.0%) |

## Replay worker evidence

The separate replay process receives a termination signal after the workload and a three-second drain interval, then writes its counters. Delivered means the entry was verified at every remote target and removed from its origin outbox. Repeated delivery is idempotent; counters include warmup and already-completed entries can be replayed again. This is not a crash-recovery or outbox-backlog acceptance test.

| Preset | Region | Delivered entries | Expired | Failed attempts |
| --- | --- | ---: | ---: | ---: |
| C | eu-central-1 | 81 | 0 | 0 |
| C | eu-west-1 | 73 | 0 | 0 |
| C | us-east-1 | 82 | 0 | 0 |
| C | us-east-2 | 70 | 0 | 0 |
| C | us-west-2 | 73 | 0 | 0 |
| E | eu-central-1 | 66 | 0 | 0 |
| E | eu-west-1 | 82 | 0 | 0 |
| E | us-east-1 | 71 | 0 | 0 |
| E | us-east-2 | 56 | 0 | 0 |
| E | us-west-2 | 76 | 0 | 0 |

## Limits and reproduction

Run IDs are `baseline-{A,B,C,D,E}-latest-1k`. Raw JSONL and per-actor summaries are retained in the private deployment artifact bucket and downloaded under ignored `spike/results/`. This report recomputes quantiles from raw samples and pools A1/A2 only within their west region; it never averages p99s. The test is a single short repetition per preset without fault injection, synchronized cross-region start, TLS, saturation testing, or a cross-client freshness observer. Fast reads can be stale. B’s best-effort background fan-out failures are not counted as foreground errors; no separate B delivery-completion metric was collected. Client command latency does not measure replication convergence. RYOW context and sequencing remain prototype implementations.

All twenty EC2 instances were stopped after measurement, as requested. EBS volumes, S3 artifacts, secrets, and Terraform infrastructure are retained; retained-service charges continue.

The sanitized [deployment manifest](deployment-20261109.json) records the measured code archive hash, installer checksum, AMIs, and live database configuration.

See [deployment and run instructions](../README.md). Regenerate with `spike/.venv/bin/python spike/scripts/report.py --input spike/results --prefix baseline- --output spike/reports/aws-baseline-20261109.md`.
