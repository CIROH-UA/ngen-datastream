#!/bin/bash
# test_ami.sh passes it to EC2 as user data, so it runs as root on the newly created test instance 


set -uo pipefail

export HOME=/root

failed_checks=0

# Usage: check "what is being checked" command [args...]
# Runs the command and records PASS if it exits 0, FAIL otherwise.
check() {
  description=$1
  shift
  if "$@" > /dev/null 2>&1; then
    echo "PASS: $description" | tee /dev/console
  else
    echo "FAIL: $description" | tee /dev/console
    failed_checks=$((failed_checks + 1))
  fi
}

# Runs a command as ec2-user
as_ec2_user() {
  runuser -u ec2-user -- "$@"
}

echo "Waiting up to 2 minutes for Docker to start..."
seconds_waited=0
until docker info > /dev/null 2>&1 || [ "$seconds_waited" -ge 120 ]; do
  sleep 5
  seconds_waited=$((seconds_waited + 5))
done

echo "=== Services ==="
check "Docker starts at boot" systemctl is-enabled docker
check "Docker is running" systemctl is-active docker
check "SSM agent is running" systemctl is-active amazon-ssm-agent
check "ec2-user can run docker" as_ec2_user docker ps

echo "=== Tools ==="
check "aws CLI is installed" aws --version
check "git is installed" git --version
check "jq is installed" jq --version
check "pigz is installed" pigz --version

echo "=== Docker images ==="
for image in $DOCKER_IMAGES; do
  check "$image is pre-pulled" docker image inspect "$image"
  image_architecture=$(docker image inspect --format '{{.Architecture}}' "$image" 2> /dev/null)
  # Production instances are Graviton (arm64). An amd64-only image would fail there.
  check "$image is built for arm64 (found: ${image_architecture:-none})" test "$image_architecture" = "arm64"
done

echo "=== datastreamcli ==="
datastreamcli_tag=$(as_ec2_user git -C /home/ec2-user/datastreamcli describe --tags --exact-match HEAD 2> /dev/null)
check "datastreamcli is at tag $DATASTREAMCLI_TAG" test "$datastreamcli_tag" = "$DATASTREAMCLI_TAG"
check "datastreamcli is owned by ec2-user" test "$(stat -c %U /home/ec2-user/datastreamcli)" = "ec2-user"
check "datastream script is executable" test -x /home/ec2-user/datastreamcli/scripts/datastream
check "restart datastream's realization file exists" test -f /home/ec2-user/datastreamcli/configs/ngen/realization_sloth_nom_cfe_pet.json

echo "=== ngen-datastream ==="
ngen_datastream_commit=$(as_ec2_user git -C /home/ec2-user/ngen-datastream rev-parse HEAD 2> /dev/null)
check "ngen-datastream is at commit $NGEN_DATASTREAM_COMMIT" test "$ngen_datastream_commit" = "$NGEN_DATASTREAM_COMMIT"
check "forcing datastream's realization file exists" test -f /home/ec2-user/ngen-datastream/configs/ngen/realization_sloth_nom_cfe_pet.json

if [ "$INCLUDE_FORCING_WEIGHTS" = "true" ]; then
  echo "=== Forcing weights ==="
  weight_file_count=$(find /home/ec2-user/hydrofabric/v2.2 -name 'nextgen_*_weights.json' 2> /dev/null | wc -l)
  check "all 21 VPU forcing weight files are present (found: $weight_file_count)" test "$weight_file_count" -eq 21
fi

if [ "$failed_checks" -eq 0 ]; then
  result="success"
else
  result="failed ($failed_checks checks failed)"
fi
echo "AMI_CHECK_RESULT=$result" | tee /dev/console
poweroff
