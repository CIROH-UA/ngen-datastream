#!/bin/bash
# THIS IS NOT COMPLETE YET. It is a draft of the test_ami.sh script, which will launch a test instance from the new AMI and run checks on it.
# Tests a newly built AMI.
#
#   1. Launch a small instance from the AMI, with check_instance.sh as its user data.
#   2. check_instance.sh checks the images, repos and files on the test instance
#   3. Print every PASS/FAIL line, and fail if any check failed.
#   4. Terminate the test instance (also on failure).
#
# This only checks what is installed on the AMI. It does not run a datastream.
# Running real datastreams on the AMI happens in the pull request that puts the
# AMI ID into prod.tfvars.
#
# Required environment variables:
#   AMI_ID                   the AMI to test
#   DATASTREAMCLI_TAG, NGEN_DATASTREAM_COMMIT, DOCKER_IMAGES, INCLUDE_FORCING_WEIGHTS
#                            the same values given to create_ami.sh
# Optional:
#   WORKFLOW_RUN             id used to tag the instance (see ami_helpers.sh)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/ami_helpers.sh"

TEST_INSTANCE_TYPE="t4g.medium"
CHECK_TIMEOUT_MINUTES=20

log "Testing AMI $AMI_ID"

echo
log "Step 1/3: Launching a test instance from the AMI"
user_data_file=$(mktemp)
write_user_data "$user_data_file" "$SCRIPT_DIR/check_instance.sh" \
  DATASTREAMCLI_TAG NGEN_DATASTREAM_COMMIT DOCKER_IMAGES INCLUDE_FORCING_WEIGHTS

test_instance_id=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type "$TEST_INSTANCE_TYPE" \
  --security-group-ids "$SECURITY_GROUP_ID" \
  --user-data "file://$user_data_file" \
  --instance-initiated-shutdown-behavior stop \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=ami-test-$AMI_ID},{Key=$WORKFLOW_RUN_TAG_KEY,Value=$WORKFLOW_RUN}]" \
  --query 'Instances[0].InstanceId' --output text)
log "Test instance: $test_instance_id"

trap 'terminate_instance "$test_instance_id"' EXIT

echo
log "Step 2/3: Waiting for check_instance.sh to finish and power the instance off"
wait_for_instance_to_stop "$test_instance_id" "$CHECK_TIMEOUT_MINUTES"

echo
log "Step 3/3: Reading the results"
check_result=$(read_result_from_console "$test_instance_id" AMI_CHECK_RESULT)

echo "Checks run on the test instance:"
get_console_output "$test_instance_id" | grep -a -o -E "(PASS|FAIL): .*" | awk '!seen[$0]++' || true
echo

if [ "$check_result" != "success" ]; then
  log "ERROR: AMI checks did not pass: $check_result"
  if [ "$check_result" = "missing" ]; then
    log "check_instance.sh never reported a result. Last 100 lines of the instance console:"
    get_console_output "$test_instance_id" | tail -n 100
  fi
  exit 1
fi

rm -f "$user_data_file"
log "All checks passed for $AMI_ID"
