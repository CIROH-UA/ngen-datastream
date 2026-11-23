#!/bin/bash
# Checks that every image the AMI will pull is on Docker Hub and has a linux/arm64 build

set -euo pipefail

# Usage: platforms_of IMAGE
# Prints the image's platforms (e.g. linux/arm64), one per line.
# Fails if the image is not on Docker Hub.
platforms_of() {
  manifest=$(docker manifest inspect "$1") || return 1
  if echo "$manifest" | jq -e 'has("manifests")' > /dev/null; then
    # multi-platform image 
    echo "$manifest" | jq -r '.manifests[].platform | select(.os != "unknown") | "\(.os)/\(.architecture)"'
  else
    # single-platform image 
    docker manifest inspect --verbose "$1" | jq -r '.Descriptor.platform | "\(.os)/\(.architecture)"'
  fi
}

failed=0
for image in $DOCKER_IMAGES; do
  if ! platforms=$(platforms_of "$image"); then
    echo "ERROR: $image is not on Docker Hub"
    failed=1
  elif ! echo "$platforms" | grep -q -x "linux/arm64"; then
    echo "ERROR: $image has no linux/arm64 build, only: $(echo "$platforms" | tr '\n' ' ')"
    failed=1
  else
    echo "OK: $image"
  fi
done

if [ "$failed" -ne 0 ]; then
  echo "Fix the image tags above and run again."
  exit 1
fi
