#!/bin/bash
# Deletes an AMI: Deletes the AMI, then deletes the EBS snapshots it was using.
# The workflow runs this when a build or test fails. It is also fine to run by hand.
#
# Usage: delete_ami.sh AMI_ID

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/ami_helpers.sh"

ami_id=$1

# Look up the snapshots first; once the AMI is deregistered we can no longer find them.
snapshot_ids=$(aws ec2 describe-images --image-ids "$ami_id" \
  --query 'Images[0].BlockDeviceMappings[].Ebs.SnapshotId' --output text)

log "Deregistering $ami_id"
aws ec2 deregister-image --image-id "$ami_id"

for snapshot_id in $snapshot_ids; do
  if [ "$snapshot_id" = "None" ]; then
    continue
  fi
  log "Deleting snapshot $snapshot_id"
  aws ec2 delete-snapshot --snapshot-id "$snapshot_id" \
    || log "WARNING: could not delete snapshot $snapshot_id, please delete it by hand"
done

log "Deleted $ami_id"
