# Docker Daemon Warm-up Optimization — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce Docker daemon warm-up time on NRDS EC2 instances by optimizing the AMI build and adding health checks to execution templates, then measure the improvement against the current AMI.

**Architecture:** Modify the AMI user-data script to write an optimized Docker daemon config, restart Docker with that config before pulling images, and pre-warm the container runtime. Add a `docker info` health check as the first command in all 4 datastream execution templates. Create a benchmarking script to compare old vs new AMI Docker startup times. Bump AMI version to trigger the CI pipeline.

**Tech Stack:** Bash (AMI script), Terraform templates (JSON), AWS CLI (benchmarking)

---

### Task 1: Add Docker daemon.json to AMI build script

**Files:**
- Modify: `shell/create_ami.sh:47-100` (inside the USER_DATA_SETUP heredoc)

**Step 1: Edit `create_ami.sh` — insert daemon.json write + Docker restart after Docker install, before image pulls**

In `shell/create_ami.sh`, locate these lines inside the `USER_DATA_SETUP` heredoc (lines 56-60):

```bash
echo "Starting Docker service..."
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

echo "Waiting for Docker to be ready..."
sleep 10
```

Replace with:

```bash
echo "Starting Docker service..."
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

echo "Waiting for Docker to be ready..."
sleep 10

echo "Writing optimized Docker daemon configuration..."
cat > /etc/docker/daemon.json << 'DOCKER_CONF'
{
  "storage-driver": "overlay2",
  "log-driver": "local",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "live-restore": true,
  "default-ulimits": {
    "nofile": { "Name": "nofile", "Hard": 65536, "Soft": 65536 }
  }
}
DOCKER_CONF

echo "Restarting Docker with optimized config..."
systemctl restart docker
sleep 5
```

**Step 2: Add pre-warm step after image pulls**

Locate these lines (lines 92-96):

```bash
echo "Pulling Docker images..."
docker pull awiciroh/datastream:$DS_TAG
docker pull awiciroh/forcingprocessor:$FP_TAG
docker pull awiciroh/ciroh-ngen-image:$NGIAB_TAG
docker pull zwills/merkdir
```

Add immediately after:

```bash
echo "Pre-warming Docker runtime..."
docker run --rm awiciroh/datastream:$DS_TAG echo "warm"
docker run --rm awiciroh/forcingprocessor:$FP_TAG echo "warm"
docker run --rm awiciroh/ciroh-ngen-image:$NGIAB_TAG echo "warm"
echo "Docker pre-warm complete"
```

**Step 3: Verify the script is syntactically valid**

Run:
```bash
bash -n shell/create_ami.sh
```

Expected: No output (exit 0 = valid syntax)

**Step 4: Commit**

```bash
git add shell/create_ami.sh
git commit -m "$(cat <<'EOF'
feat: optimize Docker daemon config in AMI build

Add /etc/docker/daemon.json with explicit overlay2 driver, local log
driver, and live-restore. Restart Docker after config so image pulls
use the optimized settings. Pre-warm Docker runtime by running a
throwaway container from each image after pulling.
EOF
)"
```

---

### Task 2: Add `docker info` health check to CFE NOM execution template

**Files:**
- Modify: `infra/aws/terraform/services/nrds/datastreams/cfe-nom/templates/execution_datastream_cfe_nom_VPU_template.json.tpl`

**Step 1: Prepend docker info command**

The current file has a single command in the `"commands"` array (line 3). Change:

```json
  "commands": [
    "runuser -l ec2-user -c 'export SKIP_VALIDATION=True DS_TAG=1.4.0 NGIAB_TAG=v1.7.0 && /home/ec2-user/datastreamcli/scripts/datastream ...'"
  ],
```

To:

```json
  "commands": [
    "runuser -l ec2-user -c 'docker info > /dev/null'",
    "runuser -l ec2-user -c 'export SKIP_VALIDATION=True DS_TAG=1.4.0 NGIAB_TAG=v1.7.0 && /home/ec2-user/datastreamcli/scripts/datastream ...'"
  ],
```

The existing long command string on line 3 stays exactly as-is. Only a new line is inserted before it.

**Step 2: Validate JSON syntax**

Run:
```bash
python3 -c "
import json, re
with open('infra/aws/terraform/services/nrds/datastreams/cfe-nom/templates/execution_datastream_cfe_nom_VPU_template.json.tpl') as f:
    content = f.read()
# Replace Terraform interpolations with dummy values so JSON parses
content = re.sub(r'\$\{[^}]+\}', 'PLACEHOLDER', content)
json.loads(content)
print('Valid JSON template')
"
```

Expected: `Valid JSON template`

**Step 3: Commit**

```bash
git add infra/aws/terraform/services/nrds/datastreams/cfe-nom/templates/execution_datastream_cfe_nom_VPU_template.json.tpl
git commit -m "feat: add docker info health check to cfe-nom execution template"
```

---

### Task 3: Add `docker info` health check to forcing execution template

**Files:**
- Modify: `infra/aws/terraform/services/nrds/datastreams/forcing/templates/execution_forcing_template.json.tpl`

**Step 1: Prepend docker info command**

The forcing template has 7 commands (lines 3-10). Insert as the new first command:

```json
  "commands": [
    "runuser -l ec2-user -c 'docker info > /dev/null'",
    "runuser -l ec2-user -c 'mkdir -p /home/ec2-user/run/datastream-metadata'",
```

All existing commands shift down by one position. No other changes.

**Step 2: Validate JSON syntax**

Run:
```bash
python3 -c "
import json, re
with open('infra/aws/terraform/services/nrds/datastreams/forcing/templates/execution_forcing_template.json.tpl') as f:
    content = f.read()
content = re.sub(r'\$\{[^}]+\}', 'PLACEHOLDER', content)
json.loads(content)
print('Valid JSON template')
"
```

Expected: `Valid JSON template`

**Step 3: Commit**

```bash
git add infra/aws/terraform/services/nrds/datastreams/forcing/templates/execution_forcing_template.json.tpl
git commit -m "feat: add docker info health check to forcing execution template"
```

---

### Task 4: Add `docker info` health check to LSTM execution template

**Files:**
- Modify: `infra/aws/terraform/services/nrds/datastreams/lstm_0/templates/execution_datastream_VPU_template.json.tpl`

**Step 1: Prepend docker info command**

Same pattern — insert before the existing single command:

```json
  "commands": [
    "runuser -l ec2-user -c 'docker info > /dev/null'",
    "runuser -l ec2-user -c 'export SKIP_VALIDATION=True DS_TAG=1.4.0 NGIAB_TAG=v1.7.0 && /home/ec2-user/datastreamcli/scripts/datastream ...'"
  ],
```

**Step 2: Validate JSON syntax**

Run:
```bash
python3 -c "
import json, re
with open('infra/aws/terraform/services/nrds/datastreams/lstm_0/templates/execution_datastream_VPU_template.json.tpl') as f:
    content = f.read()
content = re.sub(r'\$\{[^}]+\}', 'PLACEHOLDER', content)
json.loads(content)
print('Valid JSON template')
"
```

Expected: `Valid JSON template`

**Step 3: Commit**

```bash
git add infra/aws/terraform/services/nrds/datastreams/lstm_0/templates/execution_datastream_VPU_template.json.tpl
git commit -m "feat: add docker info health check to lstm_0 execution template"
```

---

### Task 5: Add `docker info` health check to routing-only execution template

**Files:**
- Modify: `infra/aws/terraform/services/nrds/datastreams/routing-only/templates/execution_datastream_routing_only_VPU_template.json.tpl`

**Step 1: Prepend docker info command**

Note: this template uses `su - ec2-user -c` instead of `runuser -l ec2-user -c`. Keep consistency with the existing style:

```json
  "commands": [
    "su - ec2-user -c 'docker info > /dev/null'",
    "su - ec2-user -c 'rm -rf /home/ec2-user/outputs && export SKIP_VALIDATION=True DS_TAG=1.4.0 NGIAB_TAG=v1.7.0 && /home/ec2-user/datastreamcli/scripts/datastream ...'"
  ],
```

**Step 2: Validate JSON syntax**

Run:
```bash
python3 -c "
import json, re
with open('infra/aws/terraform/services/nrds/datastreams/routing-only/templates/execution_datastream_routing_only_VPU_template.json.tpl') as f:
    content = f.read()
content = re.sub(r'\$\{[^}]+\}', 'PLACEHOLDER', content)
json.loads(content)
print('Valid JSON template')
"
```

Expected: `Valid JSON template`

**Step 3: Commit**

```bash
git add infra/aws/terraform/services/nrds/datastreams/routing-only/templates/execution_datastream_routing_only_VPU_template.json.tpl
git commit -m "feat: add docker info health check to routing-only execution template"
```

---

### Task 6: Create AMI benchmarking script

**Files:**
- Create: `infra/aws/shell/benchmark_docker_warmup.sh`

This script launches an EC2 instance from a given AMI, waits for it to boot, issues Docker timing commands via SSM, and reports the results. It will be used to compare the old AMI vs the new AMI.

**Step 1: Write the benchmarking script**

```bash
#!/bin/bash
# benchmark_docker_warmup.sh
# Usage: ./benchmark_docker_warmup.sh <AMI_ID> <LABEL>
# Example: ./benchmark_docker_warmup.sh ami-038132f534157b5c3 "old-ami"
#          ./benchmark_docker_warmup.sh ami-NEW123456789 "new-ami"
#
# Prerequisites: AWS CLI configured, actions_key_arm key pair exists,
#                IAM instance profile nrds_prod_ec2_profile exists.
set -euo pipefail

AMI_ID="${1:?Usage: $0 <AMI_ID> <LABEL>}"
LABEL="${2:?Usage: $0 <AMI_ID> <LABEL>}"
REGION="us-east-1"
INSTANCE_TYPE="m8g.xlarge"
KEY_NAME="actions_key_arm"
SECURITY_GROUP="sg-0fcbe0c6d6faa0117"
PROFILE_NAME="nrds_prod_ec2_profile"

echo "=== Docker Warm-up Benchmark: $LABEL ==="
echo "AMI: $AMI_ID"
echo "Instance Type: $INSTANCE_TYPE"
echo ""

# Launch instance
INSTANCE_ID=$(aws ec2 run-instances \
    --region "$REGION" \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SECURITY_GROUP" \
    --iam-instance-profile "Name=$PROFILE_NAME" \
    --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":32,"VolumeType":"gp3"}}]' \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "Instance launched: $INSTANCE_ID"
echo "Waiting for instance to be running..."
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"

BOOT_TIME=$(date +%s)
echo "Instance running at $(date)"

# Wait for SSM agent to be ready
echo "Waiting for SSM agent..."
MAX_WAIT=120
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    SSM_STATUS=$(aws ssm describe-instance-information \
        --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
        --query 'InstanceInformationList[0].PingStatus' \
        --output text 2>/dev/null || echo "None")
    if [ "$SSM_STATUS" = "Online" ]; then
        echo "SSM agent online after ${ELAPSED}s"
        break
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

if [ "$SSM_STATUS" != "Online" ]; then
    echo "ERROR: SSM agent did not come online within ${MAX_WAIT}s"
    aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID" > /dev/null
    exit 1
fi

SSM_READY_TIME=$(date +%s)

# Run benchmark commands via SSM
BENCHMARK_COMMANDS=$(cat <<'CMDS'
echo "=== BENCHMARK START ==="
echo "TIMESTAMP_BEFORE_DOCKER_INFO=$(date +%s%3N)"
docker info > /dev/null 2>&1
echo "TIMESTAMP_AFTER_DOCKER_INFO=$(date +%s%3N)"

echo "TIMESTAMP_BEFORE_DOCKER_RUN=$(date +%s%3N)"
docker run --rm awiciroh/datastream:latest echo "benchmark"
echo "TIMESTAMP_AFTER_DOCKER_RUN=$(date +%s%3N)"

echo "TIMESTAMP_BEFORE_DOCKER_RUN2=$(date +%s%3N)"
docker run --rm awiciroh/forcingprocessor:latest echo "benchmark"
echo "TIMESTAMP_AFTER_DOCKER_RUN2=$(date +%s%3N)"

echo "TIMESTAMP_BEFORE_DOCKER_RUN3=$(date +%s%3N)"
docker run --rm awiciroh/ciroh-ngen-image:latest echo "benchmark"
echo "TIMESTAMP_AFTER_DOCKER_RUN3=$(date +%s%3N)"

echo "=== BENCHMARK END ==="
CMDS
)

echo "Sending benchmark commands..."
COMMAND_ID=$(aws ssm send-command \
    --region "$REGION" \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters "commands=[\"$BENCHMARK_COMMANDS\"]" \
    --query 'Command.CommandId' \
    --output text)

echo "Command ID: $COMMAND_ID"

# Wait for command to complete
echo "Waiting for benchmark to complete..."
STATUS="InProgress"
while [ "$STATUS" = "InProgress" ] || [ "$STATUS" = "Pending" ] || [ "$STATUS" = "Delayed" ]; do
    sleep 5
    STATUS=$(aws ssm get-command-invocation \
        --command-id "$COMMAND_ID" \
        --instance-id "$INSTANCE_ID" \
        --query 'Status' \
        --output text 2>/dev/null || echo "InProgress")
done

if [ "$STATUS" != "Success" ]; then
    echo "ERROR: Benchmark command failed with status: $STATUS"
    STDERR=$(aws ssm get-command-invocation \
        --command-id "$COMMAND_ID" \
        --instance-id "$INSTANCE_ID" \
        --query 'StandardErrorContent' \
        --output text 2>/dev/null || echo "N/A")
    echo "STDERR: $STDERR"
    aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID" > /dev/null
    exit 1
fi

# Get output
OUTPUT=$(aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --query 'StandardOutputContent' \
    --output text)

echo ""
echo "=== Raw Output ==="
echo "$OUTPUT"
echo ""

# Parse timestamps and compute durations
parse_ms() { echo "$OUTPUT" | grep "$1" | head -1 | cut -d= -f2; }

T_DI_BEFORE=$(parse_ms "TIMESTAMP_BEFORE_DOCKER_INFO")
T_DI_AFTER=$(parse_ms "TIMESTAMP_AFTER_DOCKER_INFO")
T_DR1_BEFORE=$(parse_ms "TIMESTAMP_BEFORE_DOCKER_RUN=")
T_DR1_AFTER=$(parse_ms "TIMESTAMP_AFTER_DOCKER_RUN=")
T_DR2_BEFORE=$(parse_ms "TIMESTAMP_BEFORE_DOCKER_RUN2")
T_DR2_AFTER=$(parse_ms "TIMESTAMP_AFTER_DOCKER_RUN2")
T_DR3_BEFORE=$(parse_ms "TIMESTAMP_BEFORE_DOCKER_RUN3")
T_DR3_AFTER=$(parse_ms "TIMESTAMP_AFTER_DOCKER_RUN3")

DI_MS=$((T_DI_AFTER - T_DI_BEFORE))
DR1_MS=$((T_DR1_AFTER - T_DR1_BEFORE))
DR2_MS=$((T_DR2_AFTER - T_DR2_BEFORE))
DR3_MS=$((T_DR3_AFTER - T_DR3_BEFORE))
SSM_WAIT=$((SSM_READY_TIME - BOOT_TIME))

echo "=== Results: $LABEL ==="
echo "SSM agent ready:                  ${SSM_WAIT}s after boot"
echo "docker info:                      ${DI_MS}ms"
echo "docker run (datastream):          ${DR1_MS}ms"
echo "docker run (forcingprocessor):    ${DR2_MS}ms"
echo "docker run (ciroh-ngen-image):    ${DR3_MS}ms"
echo "Total first-docker-command time:  ${DI_MS}ms"
echo ""

# Terminate instance
echo "Terminating instance $INSTANCE_ID..."
aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID" > /dev/null

echo "=== Benchmark complete for $LABEL ==="
```

**Step 2: Make it executable and validate syntax**

Run:
```bash
chmod +x infra/aws/shell/benchmark_docker_warmup.sh
bash -n infra/aws/shell/benchmark_docker_warmup.sh
```

Expected: No output (exit 0)

**Step 3: Commit**

```bash
git add infra/aws/shell/benchmark_docker_warmup.sh
git commit -m "feat: add Docker warm-up benchmarking script for AMI comparison"
```

---

### Task 7: Benchmark the OLD AMI (baseline)

**Files:** None (manual execution)

**Step 1: Run benchmark against current production AMI**

The current prod AMI for CFE NOM is `ami-038132f534157b5c3` (from `infra/aws/terraform/services/nrds/envs/prod.tfvars`).

Run:
```bash
cd /Users/svemula1/Desktop/git/ngen-datastream
./infra/aws/shell/benchmark_docker_warmup.sh ami-038132f534157b5c3 "old-ami-1.6.4"
```

**Step 2: Save the output**

Redirect output to a file for later comparison:
```bash
./infra/aws/shell/benchmark_docker_warmup.sh ami-038132f534157b5c3 "old-ami-1.6.4" 2>&1 | tee /tmp/benchmark_old_ami.txt
```

Record the key metrics:
- `docker info` time (ms)
- `docker run (datastream)` time (ms)
- `docker run (forcingprocessor)` time (ms)
- `docker run (ciroh-ngen-image)` time (ms)

---

### Task 8: Bump AMI version to trigger new AMI build

**Files:**
- Modify: `ami_version.yml`

**Step 1: Bump `datastream-ami-version`**

Change:
```yaml
datastream-ami-version: "1.6.4"
```

To:
```yaml
datastream-ami-version: "1.6.5"
```

Leave `DS_TAG`, `FP_TAG`, `NGIAB_TAG` unchanged — this AMI change is about Docker config, not Docker image versions.

**Step 2: Commit**

```bash
git add ami_version.yml
git commit -m "feat: bump AMI version to 1.6.5 for Docker warm-up optimization"
```

**Note:** When this is pushed to `main`, the `build_test_create_ami.yml` workflow will automatically build the new AMI and run the full VPU test matrix. Wait for that to complete successfully before proceeding to Task 9.

---

### Task 9: Benchmark the NEW AMI

**Files:** None (manual execution)

**Step 1: Get the new AMI ID**

After the CI pipeline completes, find the new AMI:
```bash
aws ec2 describe-images \
    --owners self \
    --filters "Name=name,Values=datastream-1.6.5" \
    --query 'Images[0].ImageId' \
    --output text \
    --region us-east-1
```

**Step 2: Run benchmark against new AMI**

```bash
NEW_AMI_ID=$(aws ec2 describe-images --owners self --filters "Name=name,Values=datastream-1.6.5" --query 'Images[0].ImageId' --output text --region us-east-1)
./infra/aws/shell/benchmark_docker_warmup.sh "$NEW_AMI_ID" "new-ami-1.6.5" 2>&1 | tee /tmp/benchmark_new_ami.txt
```

**Step 3: Compare results**

```bash
echo ""
echo "========================================="
echo "  AMI Docker Warm-up Comparison"
echo "========================================="
echo ""
echo "--- OLD AMI (1.6.4) ---"
grep -E "docker info:|docker run|Total first" /tmp/benchmark_old_ami.txt
echo ""
echo "--- NEW AMI (1.6.5) ---"
grep -E "docker info:|docker run|Total first" /tmp/benchmark_new_ami.txt
echo ""
echo "========================================="
```

**Step 4: Document results**

Update the design doc with actual measured results. Edit `docs/plans/2026-03-31-docker-daemon-warmup-design.md`, replace the "Expected Impact" section with actual numbers.

**Step 5: Commit results**

```bash
git add docs/plans/2026-03-31-docker-daemon-warmup-design.md
git commit -m "docs: add measured benchmark results for Docker warm-up optimization"
```

---

### Task 10: Update prod.tfvars with new AMI ID

**Files:**
- Modify: `infra/aws/terraform/services/nrds/envs/prod.tfvars`

**Step 1: Update all AMI references that use the datastream AMI**

Only update after benchmarks confirm improvement and CI tests pass. In `prod.tfvars`, update:

```hcl
cfe_nom_ami_id      = "ami-<NEW_ID>"
routing_only_ami_id = "ami-<NEW_ID>"
lstm_0_ami_id       = "ami-<NEW_ID>"
```

Note: `fp_ami_id` uses a different AMI (`ami-062245e1c9604128d`) — only update it if the forcing processor AMI was also rebuilt.

**Step 2: Commit**

```bash
git add infra/aws/terraform/services/nrds/envs/prod.tfvars
git commit -m "feat: update prod AMI IDs to 1.6.5 with Docker warm-up optimization"
```

This commit, when merged to `main`, will trigger the `terraform-deploy.yml` workflow to update all EventBridge schedules with the new AMI.
