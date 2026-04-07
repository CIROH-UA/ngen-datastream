#!/bin/bash
set -euo pipefail

# ==============================================================================
# Test the restart datastream end-to-end via the prod state machine.
#
# What it does:
#   1. Builds the same execution payload as the terraform template
#   2. Starts a step function execution on the prod state machine
#   3. Monitors until completion
#   4. Validates channel_restart .nc file exists on S3
#   5. Cleans up test S3 output
#
# Safe for prod:
#   - Writes to test/ S3 prefix (not outputs/)
#   - Instance tagged ci_ (watchdog will catch if stuck > 3h)
#   - n_retries_allowed=0 (no retry loops)
#   - ii_terminate_instance=true (auto-cleanup)
#
# Usage: ./test_restart.sh [DATE] [INIT]
#   DATE: YYYYMMDD (default: today UTC)
#   INIT: 00-23 (default: 01)
# ==============================================================================

REGION="us-east-1"
SM_ARN="arn:aws:states:us-east-1:879381264451:stateMachine:nrds_prod_sm"
S3_BUCKET="ciroh-community-ngen-datastream"
S3_TEST_PREFIX="test/cicd/restart-test"
AMI_ID="ami-038132f534157b5c3"
INSTANCE_TYPE="m8g.xlarge"
INSTANCE_PROFILE="nrds_prod_ec2_profile"
DS_TAG="1.7.0"
FP_TAG="2.2.0"
VPU_LIST="01,02,03N,03S,03W,04,05,06,07,08,09,10L,10U,11,12,13,14,15,16,18"

DATE="${1:-$(date -u +%Y%m%d)}"
INIT="${2:-01}"
START_DATE="${DATE}${INIT}00"

echo "=== Restart Datastream Test ==="
echo "Date: $DATE | Init: $INIT | Start: $START_DATE"
echo "DS: $DS_TAG | FP: $FP_TAG"
echo "Output: s3://$S3_BUCKET/$S3_TEST_PREFIX/$INIT/"
echo ""

# Build payload — mirrors the terraform template commands exactly
cat > /tmp/restart_test_payload.json <<PAYLOAD
{
  "commands": [
    "runuser -l ec2-user -c 'mkdir -p /home/ec2-user/run/datastream-metadata'",
    "runuser -l ec2-user -c 'mkdir -p /home/ec2-user/run/ngen-run/config'",
    "runuser -l ec2-user -c 'cp /home/ec2-user/datastreamcli/configs/ngen/realization_sloth_nom_cfe_pet.json /home/ec2-user/run'",
    "runuser -l ec2-user -c 'docker run --rm -v /home/ec2-user/run:/mounted_dir -u \$(id -u):\$(id -g) -w /mounted_dir/datastream-metadata awiciroh/datastream:${DS_TAG} python3 /datastreamcli/src/datastreamcli/configure_datastream.py --docker_mount /mounted_dir --start_date ${START_DATE} --end_date ${START_DATE} --data_dir /home/ec2-user/run --forcing_source NWM_V3_ANALYSIS_ASSIM_RESTART_CHRT_${INIT} --forcing_split_vpu ${VPU_LIST} --hydrofabric_version v2.2 --realization /mounted_dir/realization_sloth_nom_cfe_pet.json --realization_provided /home/ec2-user/run/realization_sloth_nom_cfe_pet.json --s3_bucket ${S3_BUCKET} --s3_prefix ${S3_TEST_PREFIX}/${INIT}'",
    "runuser -l ec2-user -c 'docker run --rm -v /home/ec2-user/run:/mounted_dir -u \$(id -u):\$(id -g) -w /mounted_dir/datastream-metadata awiciroh/forcingprocessor:${FP_TAG} python3 /forcingprocessor/src/forcingprocessor/nwm_filenames_generator.py /mounted_dir/datastream-metadata/conf_nwmurl.json'",
    "runuser -l ec2-user -c 'cp /home/ec2-user/hydrofabric/v2.2/nextgen_*_weights.json /home/ec2-user/run'",
    "runuser -l ec2-user -c 'mv /home/ec2-user/run/filenamelist.txt /home/ec2-user/run/datastream-metadata/ 2>/dev/null || true'",
    "runuser -l ec2-user -c 'docker run --rm -e AWS_ACCESS_KEY_ID=\$(echo \$AWS_ACCESS_KEY_ID) -e AWS_SECRET_ACCESS_KEY=\$(echo \$AWS_SECRET_ACCESS_KEY) -v /home/ec2-user/run:/mounted_dir -u \$(id -u):\$(id -g) -w /mounted_dir/datastream-metadata awiciroh/forcingprocessor:${FP_TAG} python3 /forcingprocessor/src/forcingprocessor/processor.py /mounted_dir/datastream-metadata/conf_fp.json'"
  ],
  "run_options": {
    "ii_terminate_instance": true,
    "ii_delete_volume": true,
    "ii_check_s3": true,
    "ii_cheapo": true,
    "timeout_s": 1800,
    "n_retries_allowed": 0
  },
  "instance_parameters": {
    "ImageId": "${AMI_ID}",
    "InstanceType": "${INSTANCE_TYPE}",
    "IamInstanceProfile": { "Name": "${INSTANCE_PROFILE}" },
    "TagSpecifications": [
      {
        "ResourceType": "instance",
        "Tags": [
          { "Key": "Name", "Value": "ci_restart_test_init${INIT}" },
          { "Key": "Project", "Value": "ci_restart_test" }
        ]
      },
      {
        "ResourceType": "volume",
        "Tags": [
          { "Key": "Name", "Value": "ci_restart_test_init${INIT}_vol" }
        ]
      }
    ],
    "BlockDeviceMappings": [
      {
        "DeviceName": "/dev/xvda",
        "Ebs": { "VolumeSize": 64, "VolumeType": "gp3" }
      }
    ]
  }
}
PAYLOAD

echo "Starting step function execution..."
EXEC_NAME="ci_restart_test_${DATE}_init${INIT}_$(date +%s)"
EXEC_ARN=$(aws stepfunctions start-execution \
  --state-machine-arn "$SM_ARN" \
  --name "$EXEC_NAME" \
  --input "file:///tmp/restart_test_payload.json" \
  --region "$REGION" \
  --query 'executionArn' --output text)
echo "Execution: $EXEC_NAME"
echo "ARN: $EXEC_ARN"
echo ""

# Monitor
TIMEOUT=1800
ELAPSED=0
STATUS="RUNNING"
while [ "$STATUS" = "RUNNING" ] && [ $ELAPSED -lt $TIMEOUT ]; do
  STATUS=$(aws stepfunctions describe-execution \
    --execution-arn "$EXEC_ARN" --query 'status' --output text --region "$REGION")
  echo "[$ELAPSED s] $STATUS"
  if [ "$STATUS" = "RUNNING" ]; then sleep 15; ELAPSED=$((ELAPSED + 15)); fi
done

if [ "$STATUS" != "SUCCEEDED" ]; then
  echo ""
  echo "FAILED: Execution ended with status $STATUS"
  aws stepfunctions get-execution-history \
    --execution-arn "$EXEC_ARN" \
    --query "events[?type=='TaskFailed' || type=='ExecutionFailed']" \
    --output json --region "$REGION"
  exit 1
fi

echo ""
echo "=== Execution SUCCEEDED ==="
echo ""

# Validate
echo "Checking S3 for restart file..."
S3_OUTPUT=$(aws s3 ls "s3://$S3_BUCKET/$S3_TEST_PREFIX/$INIT/" --recursive --region "$REGION" 2>/dev/null || true)
NC_FILE=$(echo "$S3_OUTPUT" | grep "channel_restart.*\.nc" || true)

if [ -n "$NC_FILE" ]; then
  echo "SUCCESS: Restart file generated!"
  echo "$NC_FILE"
else
  echo "FAILED: No channel_restart .nc file found"
  echo "Files at s3://$S3_BUCKET/$S3_TEST_PREFIX/$INIT/:"
  echo "$S3_OUTPUT"
  exit 1
fi

# Cleanup
echo ""
echo "Cleaning up test output..."
aws s3 rm "s3://$S3_BUCKET/$S3_TEST_PREFIX/" --recursive --region "$REGION" --quiet || true
echo ""
echo "=== Test passed. Restart datastream is working. ==="
