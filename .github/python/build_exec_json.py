#!/usr/bin/env python3
"""
build_exec_json.py — outputs-diff matrix job helper

Reads the PR branch's execution JSON for this VPU (which already contains all
the new CLI args and env vars), substitutes the date placeholder, locks the
simulation to the baseline date, and redirects the S3 output prefix to the test
location. Then submits the job to AWS Step Functions and polls until done.

Using the PR's exec JSON directly (rather than the production one) means ALL
changed args — tags, -N paths, -F forcings, -R realizations, etc. — are
automatically picked up without any per-field substitution logic.

Reads from environment:
  TEMPLATE_FILE — path to the datastreamcli VPU template JSON
  VPU         — VPU identifier (e.g. "01", "10L")
  DATE        — baseline date YYYYMMDD
  TEST_PREFIX — S3 prefix for test output (e.g. test/outputs_diff/20250601/slug/VPU_01)
  S3_BUCKET   — S3 bucket name
  RUN_ID      — GitHub Actions run ID (used for tagging)
  SM_ARN      — Step Functions state machine ARN
  GITHUB_OUTPUT — path to GitHub Actions output file

Writes to $GITHUB_OUTPUT:
  prod_prefix — the production S3 prefix used as the comparison baseline

Writes to working directory:
  test_execution.json — ready to submit to Step Functions
"""

import boto3
import json
import os
import re
import sys
import time
from botocore.exceptions import ClientError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _short_range import apply_short_range_vars

template_file = os.environ["TEMPLATE_FILE"]
vpu           = os.environ["VPU"]
date          = os.environ["DATE"]
test_prefix   = os.environ["TEST_PREFIX"]
bucket        = os.environ.get("S3_BUCKET", "ciroh-community-ngen-datastream")
run_id        = os.environ.get("RUN_ID", "")
sm_arn        = os.environ["SM_ARN"]
gh_output     = os.environ["GITHUB_OUTPUT"]

# ── 1. Instantiate the template for this VPU at short_range/00/ ──────────────
with open(template_file) as f:
    template_data = json.load(f)

template_str = apply_short_range_vars(json.dumps(template_data), vpu)
exec_json    = json.loads(template_str)

# ── 2. Derive production S3 prefix (for downloading the baseline output) ─────
cmd = exec_json["commands"][0]
m   = re.search(r"--S3_PREFIX\s+([^\s'\"]+)", cmd)
if not m:
    print(f"ERROR: --S3_PREFIX not found in instantiated template for VPU_{vpu}")
    sys.exit(1)

prod_prefix = m.group(1).replace("ngen.DAILY", f"ngen.{date}")
print(f"Production S3 prefix: {prod_prefix}")

with open(gh_output, "a") as f:
    f.write(f"prod_prefix={prod_prefix}\n")

# ── 3. Modify the command for the test run ────────────────────────────────────
# The PR's JSON already has all the correct new arg values; we only need to:
#   a) Replace the ngen.DAILY date placeholder so the forcing path resolves to
#      the specific baseline date.
#   b) Add -e <DATE>0000 to lock the simulation end to that date.
#   c) Redirect --S3_PREFIX to the test output location.
new_commands = []
for cmd in exec_json["commands"]:
    # a) Substitute date placeholder (affects -F forcing path and any other ngen.DAILY refs)
    cmd = cmd.replace("ngen.DAILY", f"ngen.{date}")

    # b) Lock simulation end date if the command uses the DAILY start-date keyword
    if "-s DAILY" in cmd and f"-e {date}" not in cmd:
        cmd = cmd.replace("-s DAILY", f"-s DAILY -e {date}0000")

    # c) Redirect output to test S3 prefix
    cmd = re.sub(r"--S3_PREFIX [^ '\"]+", f"--S3_PREFIX {test_prefix}", cmd)

    new_commands.append(cmd)

exec_json["commands"] = new_commands

# ── 4. Set CI-friendly instance parameters ────────────────────────────────────
exec_json["instance_parameters"]["KeyName"] = "actions_key"
exec_json["instance_parameters"]["TagSpecifications"] = [
    {
        "ResourceType": "instance",
        "Tags": [{"Key": "Project", "Value": f"outputs_diff_{run_id}"}],
    }
]

with open("test_execution.json", "w") as f:
    json.dump(exec_json, f, indent=2)

print("Wrote test_execution.json")
print(f"  command preview: {new_commands[0][:400]}")

# ── 5. Ensure actions_key key pair exists ─────────────────────────────────────
ec2 = boto3.client("ec2", region_name="us-east-1")
try:
    ec2.describe_key_pairs(KeyNames=["actions_key"])
    print("Key pair 'actions_key' already exists")
except ClientError as e:
    if e.response["Error"]["Code"] != "InvalidKeyPair.NotFound":
        raise
    ec2.create_key_pair(KeyName="actions_key")
    print("Key pair 'actions_key' created")

# ── 6. Submit to Step Functions ───────────────────────────────────────────────
sfn       = boto3.client("stepfunctions", region_name="us-east-1")
exec_name = f"outputs-diff-{run_id}-VPU{vpu}-{int(time.time())}"

response = sfn.start_execution(
    stateMachineArn=sm_arn,
    name=exec_name,
    input=json.dumps(exec_json),
)
exec_arn = response["executionArn"]
print(f"Started Step Functions execution: {exec_arn}")

# ── 7. Poll until terminal state ──────────────────────────────────────────────
timeout_s = 5400  # 90-minute ceiling
elapsed   = 0
poll_s    = 30

while elapsed < timeout_s:
    desc   = sfn.describe_execution(executionArn=exec_arn)
    status = desc["status"]
    print(f"[{elapsed}s] VPU_{vpu}: {status}")

    if status == "SUCCEEDED":
        print(f"VPU_{vpu} SUCCEEDED")
        sys.exit(0)
    elif status != "RUNNING":
        print(f"ERROR: VPU_{vpu} ended with status: {status}")
        sys.exit(1)

    time.sleep(poll_s)
    elapsed += poll_s

print(f"ERROR: VPU_{vpu} timed out after {timeout_s}s")
sys.exit(1)
