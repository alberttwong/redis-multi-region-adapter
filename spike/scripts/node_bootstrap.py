#!/usr/bin/env python3
"""Runs on a spike Redis node through SSM; secrets are retrieved on the node."""
import argparse
import base64
import json
import os
import re
from pathlib import Path
import ssl
import subprocess
import tempfile
import time
import urllib.request

RLADMIN='/opt/redislabs/bin/rladmin'
CRDB='/opt/redislabs/bin/crdb-cli'

def secret(arn, region):
    return subprocess.check_output(['aws','secretsmanager','get-secret-value','--secret-id',arn,
        '--region',region,'--query','SecretString','--output','text'],text=True).strip()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--region',required=True)
    p.add_argument('--action',choices=['create','join','database','inspect','active-active'],required=True)
    p.add_argument('--node-index',type=int,default=0)
    args=p.parse_args(); inv=json.loads(args.inventory.read_text()); region=inv['regions'][args.region]
    creds=json.loads(secret(inv['admin_secret_arn'],inv['secret_region']))
    password=json.loads(secret(inv['database_secret_arn'],inv['secret_region']))['password']
    sensitive=[creds['password'], password, creds['username']]
    fqdn=args.region+'.'+inv['dns_suffix'].rstrip('.')

    def run(command, timeout=600):
        result=subprocess.run(command,capture_output=True,text=True,timeout=timeout)
        if result.returncode:
            # Never echo argv. Redact credentials and license blocks before
            # emitting a bounded diagnostic from the administrator tool.
            diagnostic = result.stdout + '\n' + result.stderr
            for value in sensitive:
                diagnostic = diagnostic.replace(value, '[REDACTED]')
            diagnostic = re.sub(r'----- LICENSE START -----.*?----- LICENSE END -----',
                                '[REDACTED LICENSE]', diagnostic, flags=re.S)
            print(json.dumps({'admin_error': diagnostic[-2000:]}))
            raise RuntimeError('redis_admin_command_failed')
        return result.stdout

    def request(path,data=None):
        # Initial trust is the certificate served by this machine's loopback API,
        # not an arbitrary remote server. Pin it for this local bootstrap session.
        certificate=ssl.get_server_certificate(('127.0.0.1',9443))
        context=ssl.create_default_context(cadata=certificate)
        context.check_hostname=False
        token=base64.b64encode((creds['username']+':'+creds['password']).encode()).decode()
        req=urllib.request.Request('https://127.0.0.1:9443/v1/'+path,
            data=None if data is None else json.dumps(data).encode(),
            headers={'Authorization':'Basic '+token,'Content-Type':'application/json'})
        with urllib.request.urlopen(req,context=context,timeout=30) as response:
            raw=response.read()
            return json.loads(raw) if raw else None

    if args.action=='create':
        if not Path('/opt/session-spike/installed').exists():raise RuntimeError('installer_not_ready')
        fd,path=tempfile.mkstemp(prefix='spike-license-',dir='/run')
        try:
            os.fchmod(fd,0o600)
            license_text=secret(inv['license_secret_arn'],inv['secret_region'])
            sensitive.extend(line for line in license_text.splitlines() if line)
            with os.fdopen(fd,'w') as out:out.write(license_text+'\n')
            run([RLADMIN,'cluster','create','name',fqdn,'username',creds['username'],
                 'password',creds['password'],'license_file',path,'addr',region['nodes'][0]['private_ip']])
        finally:os.unlink(path)
    elif args.action=='join':
        run([RLADMIN,'cluster','join','nodes',region['nodes'][0]['private_ip'],
             'username',creds['username'],'password',creds['password'],
             'addr',region['nodes'][args.node_index]['private_ip']])
    elif args.action=='database':
        names={b['name'] for b in request('bdbs')}
        if 'spike-independent' not in names:
            request('bdbs',{'name':'spike-independent','type':'redis','port':12000,
                'memory_size':3*1024**3,'replication':True,'sharding':True,'shards_count':3,
                'proxy_policy':'all-nodes','redis_version':'8.8','data_persistence':'aof',
                'aof_policy':'appendfsync-always','authentication_redis_pass':password,
                'eviction_policy':'noeviction','shard_key_regex':[
                    {'regex':r'.*\{(?<tag>.*)\}.*'},{'regex':'(?<tag>.*)'}]})
    elif args.action=='active-active':
        # Cluster admin credentials stay in the node process, never in SSM input.
        command=[CRDB,'crdb','create','--name','spike-active-active','--memory-size','3GB',
                 '--port','12001','--shards-count','3','--replication','true',
                 '--proxy-policy','all-nodes','--password',password,'--wait',
                 '--default-db-config',json.dumps({'redis_version':'8.8','data_persistence':'aof',
                    'aof_policy':'appendfsync-always','shard_key_regex':[
                    {'regex':r'.*\{(?<tag>.*)\}.*'},{'regex':'(?<tag>.*)'}]})]
        for r in inv['regions']:
            host=r+'.'+inv['dns_suffix'].rstrip('.')
            command+=['--instance',f'fqdn={host},username={creds["username"]},password={creds["password"]},url=https://{host}:9443']
        run(command,timeout=1800)
    elif args.action=='inspect':
        databases=request('bdbs')
        # Only non-secret evidence is emitted. Full BDBs contain authentication fields.
        print(json.dumps({'region':args.region,'databases':[
            {k:b.get(k) for k in ['uid','name','port','status','shards_count','replication',
                                 'redis_version','data_persistence','aof_policy','proxy_policy']}
            for b in databases if b.get('name','').startswith('spike-')]}))
        return
    print(json.dumps({'region':args.region,'action':args.action,'status':'completed'}))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'status':'failed','error_type':type(exc).__name__}))
        raise SystemExit(1)
