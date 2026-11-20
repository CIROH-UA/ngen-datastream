#!/bin/bash
# Decide what the AMI will contain, filling in any blank workflow input with a default.
#
# Inputs (environment variables, any can be blank):
#   DATASTREAMCLI_TAG  datastreamcli release tag (e.g. v1.7.4). Blank = latest release.
#   DS_TAG             awiciroh/datastream tag.         Blank = datastreamcli's versions.yml
#   FP_TAG             awiciroh/forcingprocessor tag.   Blank = datastreamcli's versions_integrations.yml
#   NGIAB_TAG          awiciroh/ciroh-ngen-image tag.   Blank = datastreamcli's versions_integrations.yml
#                      "none" for DS_TAG, FP_TAG or NGIAB_TAG leaves that image off the AMI.
#   EXTRA_IMAGES       more images to pre-pull, space separated
#   AMI_NAME           Blank = ngen-datastream-<YYYYMMDD>-run<run number>-<attempt>
#
# The tag defaults come from datastreamcli itself, so the images on the AMI are
# the ones its `datastream` script uses when DS_TAG/FP_TAG/NGIAB_TAG are not set.
#
# Outputs (written to $GITHUB_OUTPUT, or printed when run outside GitHub Actions):
#   datastreamcli_tag, docker_images, ami_name
#
# Needs the `gh` CLI (in GitHub Actions, set GH_TOKEN).

set -euo pipefail

DATASTREAMCLI_REPO="CIROH-UA/datastreamcli"

# Usage: read_version KEY FILE
# Prints the value of a line like `datastream: "1.7.4"` -> 1.7.4
read_version() {
  key=$1
  file=$2
  value=$(grep "^$key:" "$file" | cut -d'"' -f2)
  if [ -z "$value" ]; then
    echo "ERROR: no '$key' in $file" >&2
    exit 1
  fi
  echo "$value"
}

if [ -z "${DATASTREAMCLI_TAG:-}" ]; then
  DATASTREAMCLI_TAG=$(gh release view --repo "$DATASTREAMCLI_REPO" --json tagName --jq .tagName)
fi
if ! gh api "repos/$DATASTREAMCLI_REPO/git/ref/tags/$DATASTREAMCLI_TAG" --silent 2> /dev/null; then
  echo "ERROR: '$DATASTREAMCLI_TAG' is not a datastreamcli tag (see https://github.com/$DATASTREAMCLI_REPO/tags)" >&2
  exit 1
fi

versions_dir=$(mktemp -d)
raw_url="https://raw.githubusercontent.com/$DATASTREAMCLI_REPO/$DATASTREAMCLI_TAG"
curl -fsSL "$raw_url/versions.yml" -o "$versions_dir/versions.yml"
curl -fsSL "$raw_url/versions_integrations.yml" -o "$versions_dir/versions_integrations.yml"

if [ -z "${DS_TAG:-}" ]; then
  DS_TAG=$(read_version datastream "$versions_dir/versions.yml")
fi
if [ -z "${FP_TAG:-}" ]; then
  FP_TAG=$(read_version forcingprocessor "$versions_dir/versions_integrations.yml")
fi
if [ -z "${NGIAB_TAG:-}" ]; then
  NGIAB_TAG=$(read_version ciroh-ngen-image "$versions_dir/versions_integrations.yml")
fi
rm -rf "$versions_dir"

# zwills/merkdir is always included: datastreamcli runs it at the end of every datastream.
DOCKER_IMAGES="zwills/merkdir:latest"
for image in "awiciroh/datastream:$DS_TAG" "awiciroh/forcingprocessor:$FP_TAG" "awiciroh/ciroh-ngen-image:$NGIAB_TAG"; do
  if [ "${image##*:}" != "none" ]; then
    DOCKER_IMAGES="$image $DOCKER_IMAGES"
  fi
done
if [ -n "${EXTRA_IMAGES:-}" ]; then
  DOCKER_IMAGES="$DOCKER_IMAGES $EXTRA_IMAGES"
fi

if [ -z "${AMI_NAME:-}" ]; then
  AMI_NAME="ngen-datastream-$(date -u +%Y%m%d)-run${GITHUB_RUN_NUMBER:-local}-${GITHUB_RUN_ATTEMPT:-1}"
fi

outputs="datastreamcli_tag=$DATASTREAMCLI_TAG
docker_images=$DOCKER_IMAGES
ami_name=$AMI_NAME"

echo "$outputs"
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "$outputs" >> "$GITHUB_OUTPUT"
fi

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### What goes into the AMI"
    echo "| | |"
    echo "|---|---|"
    echo "| AMI name | \`$AMI_NAME\` |"
    echo "| datastreamcli | \`$DATASTREAMCLI_TAG\` |"
    echo "| ngen-datastream | \`${GITHUB_SHA:-unknown}\` |"
    echo "| Docker images | ${DOCKER_IMAGES// /<br>} |"
  } >> "$GITHUB_STEP_SUMMARY"
fi
