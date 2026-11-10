#!/usr/bin/env python3
"""Download only a spike run's result objects; credentials stay in AWS SDK."""
import argparse
import json
from pathlib import Path
import re
import boto3


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',type=Path,required=True)
    parser.add_argument('--profile',default='735486936198_SuperUserAccess')
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--output',type=Path,default=Path('spike/results'))
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',args.run_id):raise ValueError('invalid run id')
    inv=json.loads(args.inventory.read_text())
    s3=boto3.Session(profile_name=args.profile).client('s3',region_name=inv['secret_region'])
    prefix=f'results/{args.run_id}/'
    directory=args.output/args.run_id;directory.mkdir(parents=True,exist_ok=True)
    count=0
    for page in s3.get_paginator('list_objects_v2').paginate(Bucket=inv['artifact_bucket'],Prefix=prefix):
        for item in page.get('Contents',[]):
            relative=item['Key'][len(prefix):]
            if '/' in relative or not relative.endswith(('.json','.jsonl')):continue
            s3.download_file(inv['artifact_bucket'],item['Key'],str(directory/relative));count+=1
    print(json.dumps({'run_id':args.run_id,'downloaded_files':count,'directory':str(directory)}))

if __name__=='__main__':main()
