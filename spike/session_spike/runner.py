"""Regional client-side latency runner. Use `python -m session_spike.runner --help`."""
from __future__ import annotations
import argparse
import asyncio
import json
import random
import re
import signal
import time
from collections import defaultdict
from pathlib import Path
import boto3
import redis.asyncio as redis
from redis.backoff import NoBackoff
from redis.retry import Retry
from .model import Record, summarize
from .store import SnapshotMissing, SpikeStore

ACTORS = {"us-west-2": ["A1", "A2"], "us-east-1": ["B1"], "us-east-2": ["C1"],
          "eu-west-1": ["D1"], "eu-central-1": ["E1"]}
PRESETS = {"A": ("active-active", "local", False), "B": ("independent", "local", False),
           "C": ("independent", "local", True), "D": ("independent", "all-targets", False),
           "E": ("independent", "all-targets", True)}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory', type=Path, required=True)
    p.add_argument('--region', choices=ACTORS, required=True)
    p.add_argument('--preset', choices=PRESETS, required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--duration', type=float, default=60)
    p.add_argument('--warmup', type=float, default=10)
    p.add_argument('--rate', type=float, default=100, help='Scheduled operations/sec per regional runner')
    p.add_argument('--payload-bytes', type=int, default=1024)
    p.add_argument('--write-ratio', type=float, default=.2)
    p.add_argument('--policy', choices=['latest', 'required', 'any'], default='latest')
    p.add_argument('--deadline', type=float, default=2)
    p.add_argument('--poll-ms', type=float, default=10)
    p.add_argument('--max-pending', type=int, default=500)
    p.add_argument('--sessions', type=int, default=32, help='Session hashes distributed over the three server-side shards')
    p.add_argument('--ttl', type=int, default=3600)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--worker', action='store_true', help='Run durable replay only; use a separate process')
    return p.parse_args()


def make_clients(inventory: dict, mode: str, max_connections: int):
    creds = json.loads(boto3.client('secretsmanager', region_name=inventory['secret_region'])
                       .get_secret_value(SecretId=inventory['database_secret_arn'])['SecretString'])
    port = 12001 if mode == 'active-active' else 12000
    clients = {}
    for region, info in inventory['regions'].items():
        pool = redis.BlockingConnectionPool(host=info['nodes'][0]['private_ip'], port=port,
                password=creds['password'], max_connections=max_connections, timeout=5,
                socket_connect_timeout=3, socket_timeout=5, retry=Retry(NoBackoff(), 0))
        clients[region] = redis.Redis(connection_pool=pool)
    return clients


async def replay_once(store: SpikeStore, run_id: str) -> dict:
    """Recover only this run's slot-local outboxes; never scan production keys."""
    origin = store.clients[store.origin]
    counts = {'delivered': 0, 'expired': 0, 'failed': 0}
    async for key in origin.scan_iter(match=f'spike:{{{run_id}-*}}:outbox', count=100):
        entries = await origin.xrange(key, count=50)
        for entry_id, fields in entries:
            record = Record(**json.loads(fields[b'record']))
            if record.remaining_ms <= 0:
                await origin.xdel(key, entry_id)
                counts['expired'] += 1
                continue
            try:
                async with asyncio.timeout(store.timeout_s):
                    await asyncio.gather(*(store.deliver(record, r) for r in store.clients if r != store.origin))
                await origin.xdel(key, entry_id)
                # Keep run-local outbox discoverable until TTL; no unbounded empty keys.
                await origin.pexpire(key, max(1, record.remaining_ms))
                counts['delivered'] += 1
            except Exception:
                counts['failed'] += 1
    return counts


async def worker(args, inventory, clients):
    store = SpikeStore(clients, 'independent', args.region, 'local', args.deadline, args.poll_ms/1000)
    end = time.monotonic() + args.duration
    totals = {'delivered': 0, 'expired': 0, 'failed': 0}
    stop = asyncio.Event()
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stop.set)
    while time.monotonic() < end and not stop.is_set():
        for k,v in (await replay_once(store, args.run_id)).items(): totals[k] += v
        await asyncio.sleep(.05)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'region':args.region,'worker':totals},indent=2)+'\n')


async def workload(args, inventory, clients):
    mode, ack, capture = PRESETS[args.preset]
    store = SpikeStore(clients, mode, args.region, ack, args.deadline, args.poll_ms/1000)
    actors = ACTORS[args.region]
    queues = {actor:asyncio.Queue(maxsize=args.max_pending) for actor in actors}
    rows = []
    start = time.perf_counter()
    measure_start = start + args.warmup
    stop = measure_start + args.duration

    async def actor_loop(actor):
        # Context belongs only to this actor; never share A1's context with A2/B1/etc.
        floors = {}
        seqs = defaultdict(int)
        rng = random.Random(args.run_id + actor)
        while True:
            scheduled = await queues[actor].get()
            if scheduled is None:
                return
            actual_start = time.perf_counter()
            slot = rng.randrange(args.sessions)
            session = f'{args.run_id}-s{slot}'
            operation = 'write' if rng.random() < args.write_ratio else 'read'
            outcome = 'success'
            result_sequence = None
            try:
                if operation == 'write':
                    seqs[session] += 1
                    record = Record.new(session, actor, seqs[session], 'x'*args.payload_bytes, args.ttl)
                    await store.write(record, capture=capture)
                    floors[session] = record
                    result_sequence = record.sequence
                else:
                    # An independent actor with no own write requirement is unprotected.
                    result = await store.read(args.region,session,args.policy,floors.get(session))
                    if result is None: outcome = 'null'
                    else: result_sequence = result.sequence
            except SnapshotMissing:
                outcome = 'snapshot_missing'
            except TimeoutError:
                outcome = 'partial_or_timeout' if operation == 'write' else 'timeout'
            except ValueError as exc:
                outcome = str(exc) if str(exc) in {'expired','context_required','identity_conflict','integrity_error'} else 'validation_error'
            except Exception as exc:
                # Never record exception messages, which may include endpoints or credentials.
                outcome = 'infrastructure_error'
            done = time.perf_counter()
            if scheduled >= measure_start:
                rows.append({'actor':actor,'region':args.region,'group':inventory['regions'][args.region]['group'],
                    'operation':operation,'policy':args.policy,'preset':args.preset,'outcome':outcome,
                    'protected':session in floors,'sequence':result_sequence,
                    'latency_ms':(done-scheduled)*1000,'service_ms':(done-actual_start)*1000,
                    'schedule_lag_ms':(actual_start-scheduled)*1000})

    tasks = [asyncio.create_task(actor_loop(a)) for a in actors]
    index=0
    while True:
        scheduled = start + index/args.rate
        if scheduled >= stop:break
        await asyncio.sleep(max(0,scheduled-time.perf_counter()))
        actor = actors[index % len(actors)]
        try:
            queues[actor].put_nowait(scheduled)
        except asyncio.QueueFull:
            if scheduled >= measure_start:
                rows.append({'actor':actor,'region':args.region,'operation':'not_executed','policy':args.policy,
                    'preset':args.preset,'outcome':'generator_overload','protected':False,
                    'latency_ms':(time.perf_counter()-scheduled)*1000})
        index+=1
    for q in queues.values():await q.put(None)
    await asyncio.gather(*tasks)
    await store.close()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('w') as out:
        for row in rows:out.write(json.dumps(row,separators=(',',':'))+'\n')
    groups=defaultdict(list)
    for row in rows:groups[(row['actor'],row['operation'],row['policy'],row['protected'])].append(row)
    result={'metadata':{'redis_software_build':inventory['redis_version'],'region':args.region,
        'preset':args.preset,'distribution':mode,'acknowledgment':ack,'replay_capture':capture,
        'payload_bytes':args.payload_bytes,'scheduled_rate':args.rate,'warmup_s':args.warmup,
        'duration_s':args.duration,'sessions':args.sessions,'primary_shards':3,
        'data_tls':False,'load_model':'scheduled arrivals; serialized per actor; bounded queues',
        'scope':'experimental latency harness; not production context security/consensus'},
        'groups':[{'actor':key[0],'operation':key[1],'policy':key[2],'protected':key[3],**summarize(rs)} for key,rs in groups.items()]}
    args.output.with_suffix('.summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'output':str(args.output),'samples':len(rows),'region':args.region}))


async def main_async(args):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',args.run_id):raise ValueError('invalid run id')
    if args.rate <= 0 or args.duration <= 0 or args.warmup < 0 or args.sessions < 1 or args.max_pending < 1 or args.deadline <= 0 or args.poll_ms <= 0 or not 0 <= args.write_ratio <= 1:
        raise ValueError('invalid load configuration')
    if args.payload_bytes < 1 or args.ttl <= args.duration+args.warmup+args.deadline:
        raise ValueError('payload must be positive and TTL must cover the run')
    inventory=json.loads(args.inventory.read_text())
    mode=PRESETS[args.preset][0]
    clients=make_clients(inventory,mode,max_connections=32)
    try:
        # Preflight the same local path, without manufacturing a version context.
        await clients[args.region].ping()
        if args.worker:await worker(args,inventory,clients)
        else:await workload(args,inventory,clients)
    finally:
        await asyncio.gather(*(c.aclose() for c in clients.values()))
        await asyncio.gather(*(c.connection_pool.disconnect() for c in clients.values()))

if __name__=='__main__':
    asyncio.run(main_async(parse_args()))
