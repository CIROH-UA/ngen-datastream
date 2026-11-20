#!/bin/bash
# Builds the NRDS datastream AMI.
#
#   1. Launch a temporary arm64 instance from the latest Amazon Linux 2023 image,
#      with setup_instance.sh as its user data.
#   2. setup_instance.sh installs everything and powers the instance off.
#   3. Once the instance has stopped, check that setup_instance.sh reported
#      success, then create the AMI from the stopped instance.
#   4. Terminate the temporary instance (also on failure).
#
# Required environment variables:
#   AMI_NAME                 name for the new AMI (must not already exist)
#   DATASTREAMCLI_TAG        datastreamcli release tag to install
#   NGEN_DATASTREAM_COMMIT   ngen-datastream commit to install
#   DOCKER_IMAGES            space separated images to pre-pull
#   INCLUDE_FORCING_WEIGHTS  "true" or "false"
# Optional:
#   BUILT_BY                 where the build ran (the workflow sets its run URL)
#   WORKFLOW_RUN             id used to tag the instance (see ami_helpers.sh)
#
# When run in GitHub Actions, it writes ami_id=<id> to $GITHUB_OUTPUT.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/ami_helpers.sh"

BUILT_BY="${BUILT_BY:-$(whoami) on $(hostname)}"

BUILD_INSTANCE_TYPE="t4g.large"
BASE_IMAGE_PARAMETER="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
ROOT_VOLUME_GB=32
SETUP_TIMEOUT_MINUTES=45
AMI_AVAILABLE_TIMEOUT_MINUTES=45

log "Building AMI $AMI_NAME"
log "  datastreamcli tag:      $DATASTREAMCLI_TAG"
log "  ngen-datastream commit: $NGEN_DATASTREAM_COMMIT"
log "  docker images:          $DOCKER_IMAGES"
log "  forcing weights:        $INCLUDE_FORCING_WEIGHTS"

echo
log "Step 1/5: Checking the AMI name is free"
existing_ami_id=$(aws ec2 describe-images --owners self \
  --filters "Name=name,Values=$AMI_NAME" \
  --query 'Images[0].ImageId' --output text)
if [ "$existing_ami_id" != "None" ]; then
  log "ERROR: an AMI named $AMI_NAME already exists ($existing_ami_id). Choose another name."
  exit 1
fi

echo
log "Step 2/5: Launching the build instance"
base_ami_id=$(aws ssm get-parameter --name "$BASE_IMAGE_PARAMETER" --query Parameter.Value --output text)
log "Base image: $base_ami_id"

user_data_file=$(mktemp)
write_user_data "$user_data_file" "$SCRIPT_DIR/setup_instance.sh" \
  DATASTREAMCLI_TAG NGEN_DATASTREAM_COMMIT DOCKER_IMAGES INCLUDE_FORCING_WEIGHTS

build_instance_id=$(aws ec2 run-instances \
  --image-id "$base_ami_id" \
  --instance-type "$BUILD_INSTANCE_TYPE" \
  --security-group-ids "$SECURITY_GROUP_ID" \
  --user-data "file://$user_data_file" \
  --instance-initiated-shutdown-behavior stop \
  --block-device-mappings "[{\"DeviceName\":\"/dev/xvda\",\"Ebs\":{\"VolumeSize\":$ROOT_VOLUME_GB,\"VolumeType\":\"gp3\"}}]" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=ami-builder-$AMI_NAME},{Key=$WORKFLOW_RUN_TAG_KEY,Value=$WORKFLOW_RUN}]" \
  --query 'Instances[0].InstanceId' --output text)
log "Build instance: $build_instance_id"

trap 'terminate_instance "$build_instance_id"' EXIT

echo
log "Step 3/5: Waiting for setup_instance.sh to finish and power the instance off"
wait_for_instance_to_stop "$build_instance_id" "$SETUP_TIMEOUT_MINUTES"

setup_result=$(read_result_from_console "$build_instance_id" AMI_SETUP_RESULT)
log "setup_instance.sh result: $setup_result"
if [ "$setup_result" != "success" ]; then
  log "ERROR: setup did not succeed. Last 100 lines of the instance console:"
  get_console_output "$build_instance_id" | tail -n 100
  exit 1
fi

echo
log "Step 4/5: Creating the AMI from the stopped instance"
# Tags record what went into the AMI, so anyone can look it up later.
# AWS limits tag values to 256 characters.
tags=$(jq -n -c \
  --arg name "$AMI_NAME" \
  --arg datastreamcli_tag "$DATASTREAMCLI_TAG" \
  --arg ngen_datastream_commit "$NGEN_DATASTREAM_COMMIT" \
  --arg docker_images "${DOCKER_IMAGES:0:256}" \
  --arg forcing_weights "$INCLUDE_FORCING_WEIGHTS" \
  --arg built_by "${BUILT_BY:0:256}" \
  '[
    {Key: "Name",                   Value: $name},
    {Key: "datastreamcli-tag",      Value: $datastreamcli_tag},
    {Key: "ngen-datastream-commit", Value: $ngen_datastream_commit},
    {Key: "docker-images",          Value: $docker_images},
    {Key: "forcing-weights",        Value: $forcing_weights}
  ]')
tag_specifications=$(jq -n -c --argjson tags "$tags" \
  '[{ResourceType: "image", Tags: $tags}, {ResourceType: "snapshot", Tags: $tags}]')

ami_id=$(aws ec2 create-image \
  --instance-id "$build_instance_id" \
  --name "$AMI_NAME" \
  --description "NRDS datastream AMI. See its tags for what is installed." \
  --tag-specifications "$tag_specifications" \
  --query ImageId --output text)
log "AMI: $ami_id"

# Report the ID right away, so the workflow can delete the AMI if a later step fails.
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "ami_id=$ami_id" >> "$GITHUB_OUTPUT"
fi

echo
log "Step 5/5: Waiting for the AMI to become available"
started_at=$(date +%s)
while true; do
  ami_state=$(aws ec2 describe-images --image-ids "$ami_id" --query 'Images[0].State' --output text)
  minutes_waited=$(( ($(date +%s) - started_at) / 60 ))
  log "$ami_id is $ami_state ($minutes_waited min)"

  if [ "$ami_state" = "available" ]; then
    break
  fi
  if [ "$ami_state" = "failed" ]; then
    log "ERROR: AWS failed to create $ami_id"
    exit 1
  fi
  if [ "$minutes_waited" -ge "$AMI_AVAILABLE_TIMEOUT_MINUTES" ]; then
    log "ERROR: $ami_id was not available within $AMI_AVAILABLE_TIMEOUT_MINUTES minutes"
    exit 1
  fi
  sleep 30
done

rm -f "$user_data_file"
log "Done. AMI $ami_id ($AMI_NAME) is available."
