#!/bin/bash
# create_ami.sh passes this file to EC2 as user data, so it runs as root on the build instance when that instance boots.
# create_ami.sh puts these variables at the top of the file before sending it:
#   DATASTREAMCLI_TAG        datastreamcli release tag to put in /home/ec2-user/datastreamcli
#   NGEN_DATASTREAM_COMMIT   ngen-datastream commit to put in /home/ec2-user/ngen-datastream
#   DOCKER_IMAGES            space separated images to pre-pull
#   INCLUDE_FORCING_WEIGHTS  "true" to copy the v2.2 forcing weights to /home/ec2-user/hydrofabric/v2.2
#
# When it finishes, it prints "AMI_SETUP_RESULT=success" (or "failed ...") to the
# EC2 console and powers the instance off. create_ami.sh waits for the instance
# to stop, reads that line from the console, and only then creates the AMI.

set -euo pipefail

export HOME=/root

report_result_and_power_off() {
  exit_code=$?
  if [ "$exit_code" -eq 0 ]; then
    result="success"
  else
    result="failed (exit code $exit_code)"
  fi
  echo "AMI_SETUP_RESULT=$result" | tee /dev/console || true
  poweroff
}
trap report_result_and_power_off EXIT

# Fetches one commit or tag instead of cloning the whole history, so the AMI stays minimal
clone_repo_at() {
  repo_url=$1
  target_dir=$2
  ref=$3
  git init -q "$target_dir"
  git -C "$target_dir" remote add origin "$repo_url"
  git -C "$target_dir" fetch -q --depth 1 origin "$ref"
  git -C "$target_dir" checkout -q FETCH_HEAD
}

echo "=== Setup started at $(date -u) ==="
echo "DATASTREAMCLI_TAG=$DATASTREAMCLI_TAG"
echo "NGEN_DATASTREAM_COMMIT=$NGEN_DATASTREAM_COMMIT"
echo "DOCKER_IMAGES=$DOCKER_IMAGES"
echo "INCLUDE_FORCING_WEIGHTS=$INCLUDE_FORCING_WEIGHTS"

echo "=== Installing system packages ==="
dnf update -y
dnf install -y git docker jq pigz python3-pip tar wget awscli

echo "=== Starting Docker ==="
systemctl enable --now docker
usermod -aG docker ec2-user

echo "=== Installing datastreamcli ==="
# The cfe-nom, lstm_0, routing-only and restart datastreams run scripts and configs from here.
clone_repo_at https://github.com/CIROH-UA/datastreamcli.git /home/ec2-user/datastreamcli "refs/tags/$DATASTREAMCLI_TAG:refs/tags/$DATASTREAMCLI_TAG"

echo "=== Installing ngen-datastream ==="
# The forcing datastream copies its realization file from here.
clone_repo_at https://github.com/CIROH-UA/ngen-datastream.git /home/ec2-user/ngen-datastream "$NGEN_DATASTREAM_COMMIT"

if [ "$INCLUDE_FORCING_WEIGHTS" = "true" ]; then
  echo "=== Copying v2.2 forcing weights ==="
  # The forcing datastream copies nextgen_*_weights.json from this folder.
  aws s3 cp --recursive --no-sign-request --no-progress --region us-east-1 \
    s3://ciroh-community-ngen-datastream/resources/v2.2_hydrofabric/weights/ \
    /home/ec2-user/hydrofabric/v2.2/
fi

chown -R ec2-user:ec2-user /home/ec2-user

echo "=== Pulling Docker images ==="
for image in $DOCKER_IMAGES; do
  docker pull "$image"
done

echo "=== Cleaning up ==="
dnf clean all

echo "=== Setup finished at $(date -u) ==="
