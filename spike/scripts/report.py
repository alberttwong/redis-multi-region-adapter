#!/usr/bin/env python3
"""Produce a descriptive report from raw samples, never average host quantiles."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from session_spike.model import percentile


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=Path('spike/results'))
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prefix',default='baseline-')
    args=p.parse_args();groups=defaultdict(list);metadata=[];workers=[]
    for directory in sorted(args.input.glob(args.prefix+'*')):
        for file in sorted(directory.glob('*.jsonl')):
            for line in file.open():
                row=json.loads(line)
                condition=('protected' if row['protected'] else 'unprotected') if row['operation']=='read' else 'write'
                groups[(row['preset'],row['region'],row['operation'],condition)].append(row)
        for file in sorted(directory.glob('*.summary.json')):
            metadata.append(json.loads(file.read_text())['metadata'])
        for file in sorted(directory.glob('*.worker.json')):
            workers.append({'preset':directory.name.split('-')[1],**json.loads(file.read_text())})
    if not groups:raise SystemExit('No matching samples')
    lines=['# AWS latency baseline — 2026-11-09','',
        'These are live five-region AWS measurements of the experimental adapter. They are descriptive samples, not a production SLO or proof of strict geographic consistency. Every group below has fewer than 10,000 samples; p99 is particularly sensitive to individual observations.','',
        'A = native Active-Active/local acknowledgment; B = independent/request-only/local; C = independent/replay/local; D = independent/request-only/all five targets; E = independent/replay/all five targets. All use default `latest`: locally selected state with each caller’s own RYOW context. Independent clients do not receive another writer’s context.','',
        '## Configuration','',
        'Redis Software 8.2.6-25; Redis database 8.8; three primary shards plus replication per database and region; AOF `appendfsync-always`; 15 m6i.xlarge Redis nodes and five c6i.large runners. Both database types share the same hardware; presets ran sequentially. Private peered data paths use authentication without client TLS. Six serialized actors exercise 32 shared synthetic sessions, 1 KiB payload, 20% writes, 10-second warmup and 60-second measurement, with five scheduled operations/second per regional runner (west split between A1/A2). These are low-load latency probes, not capacity tests.','',
        'Latencies include scheduling delay, adapter work, connection pool, Redis, and network. All-target writes verify the immutable copy at all four remote targets with a GET after delivery. This deliberately costs an additional phase; it is an adapter placement barrier, not a consensus commit. Protected reads may fall back to their exact own-write version when the local discovery candidate has incomparable lineage. Null unprotected reads are reported explicitly. Because each actor serializes reads and writes, a long WAN write delays later scheduled reads: D/E read response tails can include client head-of-line blocking. Service p99 separates actual operation time from that generator queue; a concurrent-request production model requires a separate run.','',
        '## Samples by path','',
        '| Preset | Origin | Path | n | p50 ms | p95 ms | p99 ms | Service p99 ms | Outcomes |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for (preset,region,operation,condition),rows in sorted(groups.items()):
        values=[r['latency_ms'] for r in rows]
        q=[percentile(values,f) for f in [.5,.95,.99]]
        service=percentile([r['service_ms'] for r in rows if 'service_ms' in r],.99)
        outcomes=', '.join(f'{k}={v} ({v/len(rows):.1%})' for k,v in sorted(Counter(r['outcome'] for r in rows).items()))
        lines.append(f'| {preset} | {region} | {operation} {condition if operation=="read" else ""} | {len(rows)} | {q[0]:.2f} | {q[1]:.2f} | {q[2]:.2f} | {service:.2f} | {outcomes} |')
    regional=defaultdict(list)
    for (preset,region,operation,condition),rows in groups.items():
        regional[(preset,region,operation)].extend(rows)
    overview=['## Regional p99 ranges','',
        'Each range spans the five individual regional p99s; it is not a pooled percentile. Service time excludes generator scheduling delay. Counts and outcomes below remain the authoritative detail.','',
        '| Preset | Read response p99 range ms | Write response p99 range ms | Write service p99 range ms |',
        '| --- | ---: | ---: | ---: |']
    for preset in sorted({key[0] for key in regional}):
        ranges=[]
        for operation,field in [('read','latency_ms'),('write','latency_ms'),('write','service_ms')]:
            values=[percentile([r[field] for r in rows],.99) for (p,region,op),rows in regional.items() if p==preset and op==operation]
            ranges.append(f'{min(values):.2f}–{max(values):.2f}')
        overview.append('| '+preset+' | '+' | '.join(ranges)+' |')
    outcomes=Counter(r['outcome'] for rows in groups.values() for r in rows)
    lines[2:2]=['Measured foreground outcomes: '+', '.join(f'{k}={v}' for k,v in sorted(outcomes.items()))+'. Warmup operations are excluded.', '']
    at=lines.index('## Samples by path')
    lines[at:at]=overview+['']
    if workers:
        lines += ['', '## Replay worker evidence','',
            'The separate replay process receives a termination signal after the workload and a three-second drain interval, then writes its counters. Delivered means the entry was verified at every remote target and removed from its origin outbox. Repeated delivery is idempotent; counters include warmup and already-completed entries can be replayed again. This is not a crash-recovery or outbox-backlog acceptance test.','',
            '| Preset | Region | Delivered entries | Expired | Failed attempts |',
            '| --- | --- | ---: | ---: | ---: |']
        totals=defaultdict(Counter)
        for worker in workers:totals[(worker['preset'],worker['region'])].update(worker['worker'])
        for (preset,region),c in sorted(totals.items()):lines.append(f'| {preset} | {region} | {c["delivered"]} | {c["expired"]} | {c["failed"]} |')
    lines += ['', '## Limits and reproduction','',
        'Run IDs are `baseline-{A,B,C,D,E}-latest-1k`. Raw JSONL and per-actor summaries are retained in the private deployment artifact bucket and downloaded under ignored `spike/results/`. This report recomputes quantiles from raw samples and pools A1/A2 only within their west region; it never averages p99s. The test is a single short repetition per preset without fault injection, synchronized cross-region start, TLS, saturation testing, or a cross-client freshness observer. Fast reads can be stale. B’s best-effort background fan-out failures are not counted as foreground errors; no separate B delivery-completion metric was collected. Client command latency does not measure replication convergence. RYOW context and sequencing remain prototype implementations.','',
        'All twenty EC2 instances were stopped after measurement, as requested. EBS volumes, S3 artifacts, secrets, and Terraform infrastructure are retained; retained-service charges continue.', '',
        'The sanitized [deployment manifest](deployment-20261109.json) records the measured code archive hash, installer checksum, AMIs, and live database configuration.', '',
        'See [deployment and run instructions](../README.md). Regenerate with `spike/.venv/bin/python spike/scripts/report.py --input spike/results --prefix baseline- --output spike/reports/aws-baseline-20261109.md`.','']
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text('\n'.join(lines))
    print(json.dumps({'output':str(args.output),'groups':len(groups),'samples':sum(map(len,groups.values())),'regional_runs':len(metadata)}))

if __name__=='__main__':main()
