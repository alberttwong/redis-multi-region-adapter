#!/usr/bin/env python3
"""Upload/bootstrap/run spike resources through SSM. No SSH or secrets in commands."""
import argparse
import concurrent.futures
import hashlib
import io
import json
from pathlib import Path
import shlex
import tarfile
import time
import boto3

ROOT=Path(__file__).resolve().parents[1]

def ssm_run(session,region,instance,commands,timeout=1800):
    client=session.client('ssm',region_name=region)
    response=client.send_command(InstanceIds=[instance],DocumentName='AWS-RunShellScript',
        Parameters={'commands':['bash -c '+shlex.quote('\n'.join(commands))],'executionTimeout':[str(timeout)]},TimeoutSeconds=60)
    command=response['Command']['CommandId'];end=time.monotonic()+timeout+60
    while time.monotonic()<end:
        try:result=client.get_command_invocation(CommandId=command,InstanceId=instance)
        except client.exceptions.InvocationDoesNotExist:
            time.sleep(1);continue
        if result['Status'] in {'Success','Failed','TimedOut','Cancelled'}:
            return {'region':region,'instance':instance,'command_id':command,'status':result['Status'],
                    'stdout':result.get('StandardOutputContent','')[-6000:]}
        time.sleep(2)
    return {'region':region,'instance':instance,'command_id':command,'status':'ControllerTimeout'}


def upload(session,inv,path):
    bucket=inv['artifact_bucket'];s3=session.client('s3',region_name=inv['secret_region'])
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode='w:gz') as tar:
        for directory in ['session_spike','scripts']:
            for file in (ROOT/directory).rglob('*.py'):
                tar.add(file,arcname=str(file.relative_to(ROOT)))
    blob=archive.getvalue();digest=hashlib.sha256(blob).hexdigest()
    key=f'code/{digest}.tar.gz';s3.put_object(Bucket=bucket,Key=key,Body=blob)
    inv['code_key']=key; inv['code_sha256']=digest
    inv['inventory_key']=f'config/{digest}.json'
    s3.put_object(Bucket=bucket,Key=inv['inventory_key'],Body=json.dumps(inv).encode())
    path.write_text(json.dumps(inv,indent=2)+'\n')
    print(json.dumps({'uploaded_code':key,'inventory_key':inv['inventory_key']}))


def bootstrap_command(inv,region,action,index):
    bucket=inv['artifact_bucket'];quote=shlex.quote
    return ['set -euo pipefail','mkdir -p /opt/session-spike',
        f'aws s3 cp {quote("s3://"+bucket+"/"+inv["code_key"])} /opt/session-spike/code.tar.gz --region {inv["secret_region"]}',
        f'echo {quote(inv["code_sha256"]+"  /opt/session-spike/code.tar.gz")} | sha256sum -c -',
        'tar xzf /opt/session-spike/code.tar.gz -C /opt/session-spike',
        f'aws s3 cp {quote("s3://"+bucket+"/"+inv["inventory_key"])} /opt/session-spike/inventory.json --region {inv["secret_region"]}',
        'python3 /opt/session-spike/scripts/node_bootstrap.py --inventory /opt/session-spike/inventory.json '+
        f'--region {quote(region)} --action {quote(action)} --node-index {index}']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--profile',default='735486936198_SuperUserAccess')
    p.add_argument('action',choices=['upload','ready','create','join','database','inspect','active-active','run'])
    p.add_argument('--preset',choices=list('ABCDE'),default='B')
    p.add_argument('--run-id',default='smoke')
    p.add_argument('--duration',type=int,default=60)
    p.add_argument('--rate',type=int,default=100)
    p.add_argument('--policy',choices=['latest','required','any'],default='latest')
    p.add_argument('--payload-bytes',type=int,default=1024)
    p.add_argument('--write-ratio',type=float,default=.2)
    args=p.parse_args();inv=json.loads(args.inventory.read_text());session=boto3.Session(profile_name=args.profile)
    if args.action=='upload':upload(session,inv,args.inventory);return
    jobs=[]
    for region,info in inv['regions'].items():
        if args.action=='active-active' and region!='us-west-2':continue
        if args.action=='run':
            bucket=inv['artifact_bucket'];q=shlex.quote;dest=f'/opt/session-spike/results/{args.run_id}-{region}.jsonl'
            commands=['set -euo pipefail','mkdir -p /opt/session-spike/results',
                f'aws s3 cp {q("s3://"+bucket+"/"+inv["code_key"])} /opt/session-spike/code.tar.gz --region {inv["secret_region"]}',
                f'echo {q(inv["code_sha256"]+"  /opt/session-spike/code.tar.gz")} | sha256sum -c -',
                'tar xzf /opt/session-spike/code.tar.gz -C /opt/session-spike',
                f'aws s3 cp {q("s3://"+bucket+"/"+inv["inventory_key"])} /opt/session-spike/inventory.json --region {inv["secret_region"]}']
            common=f'--inventory /opt/session-spike/inventory.json --region {q(region)} --preset {q(args.preset)} --run-id {q(args.run_id)} --deadline 2'
            if args.preset in 'CE':
                # A separate process preserves Redis outbox replay after a writer exits.
                commands += ['cd /opt/session-spike',f'PYTHONPATH=/opt/session-spike nohup /opt/session-spike-venv/bin/python -m session_spike.runner {common} --worker --duration {args.duration+120} --output {q(dest+".worker.json")} >/opt/session-spike/worker.log 2>&1 &\nworker_pid=$!']
            commands += [f'PYTHONPATH=/opt/session-spike /opt/session-spike-venv/bin/python -m session_spike.runner {common} --duration {args.duration} --rate {args.rate} --policy {q(args.policy)} --payload-bytes {args.payload_bytes} --write-ratio {args.write_ratio} --output {q(dest)}',
                f'aws s3 cp {q(dest)} {q("s3://"+bucket+"/results/"+args.run_id+"/"+region+".jsonl")} --region {inv["secret_region"]}',
                f'aws s3 cp {q(dest.replace(".jsonl",".summary.json"))} {q("s3://"+bucket+"/results/"+args.run_id+"/"+region+".summary.json")} --region {inv["secret_region"]}']
            if args.preset in 'CE':
                commands += ['sleep 3', 'kill -TERM "$worker_pid"', 'wait "$worker_pid"',
                    f'aws s3 cp {q(dest+".worker.json")} {q("s3://"+bucket+"/results/"+args.run_id+"/"+region+".worker.json")} --region {inv["secret_region"]}']
            jobs.append((region,info['runner']['id'],commands,args.duration+300))
        elif args.action=='ready':
            for node in info['nodes']:
                jobs.append((region,node['id'],['for attempt in {1..30}; do if test -f /opt/session-spike/installed; then echo installed; exit 0; fi; sleep 10; done; exit 1'],360))
            jobs.append((region,info['runner']['id'],['set -e',
                'test -x /opt/session-spike-venv/bin/python',
                '/opt/session-spike-venv/bin/python -c "import sys,redis,boto3; assert sys.version_info >= (3, 11); print(\'runner-ready\')"',
                'command -v aws'],60))
        else:
            nodes=list(enumerate(info['nodes'])) if args.action=='join' else [(0,info['nodes'][0])]
            for index,node in nodes:
                if args.action=='join' and index==0:continue
                jobs.append((region,node['id'],bootstrap_command(inv,region,args.action,index),1800))
    failed=False
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures=[executor.submit(ssm_run,session,*job) for job in jobs]
        for future in concurrent.futures.as_completed(futures):
            result=future.result();print(json.dumps(result),flush=True)
            failed |= result['status']!='Success'
    raise SystemExit(1 if failed else 0)

if __name__=='__main__':main()
