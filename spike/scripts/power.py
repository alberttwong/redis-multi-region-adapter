#!/usr/bin/env python3
"""Stop or start only inventory instances after account and namespace checks."""
import argparse
import concurrent.futures
import json
from pathlib import Path
import boto3


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--profile',default='735486936198_SuperUserAccess')
    p.add_argument('action',choices=['stop','start'])
    args=p.parse_args();inv=json.loads(args.inventory.read_text())
    session=boto3.Session(profile_name=args.profile)
    if session.client('sts').get_caller_identity()['Account']!=inv['account_id']:
        raise RuntimeError('account_mismatch')

    def region_action(region,info):
        client=session.client('ec2',region_name=region)
        ids=[n['id'] for n in info['nodes']]+[info['runner']['id']]
        response=client.describe_instances(InstanceIds=ids)
        instances=[i for r in response['Reservations'] for i in r['Instances']]
        if len(instances)!=4:raise RuntimeError('inventory_mismatch')
        for instance in instances:
            tags={tag['Key']:tag['Value'] for tag in instance.get('Tags',[])}
            if not tags.get('Name','').startswith(inv['deployment_name']+'-'):
                raise RuntimeError('namespace_mismatch')
        if args.action=='stop':
            client.stop_instances(InstanceIds=ids)
            waiter='instance_stopped'
        else:
            client.start_instances(InstanceIds=ids)
            waiter='instance_running'
        client.get_waiter(waiter).wait(InstanceIds=ids,WaiterConfig={'Delay':10,'MaxAttempts':30})
        return {'region':region,'instances':len(ids),'state':'stopped' if args.action=='stop' else 'running'}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures=[executor.submit(region_action,r,i) for r,i in inv['regions'].items()]
        for future in concurrent.futures.as_completed(futures):print(json.dumps(future.result()),flush=True)

if __name__=='__main__':main()
