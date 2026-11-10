#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -o Acquire::Retries=5
apt-get install -y python3-venv curl unzip jq ca-certificates
python3 -m venv /opt/session-spike-venv
/opt/session-spike-venv/bin/pip install 'redis==6.4.0' 'boto3>=1.40,<2'
curl --fail --location --retry 3 https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscli.zip
unzip -q /tmp/awscli.zip -d /tmp/awscli-install
/tmp/awscli-install/aws/install
mkdir -p /opt/session-spike
