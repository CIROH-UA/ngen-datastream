#!/bin/bash
# Prints a markdown report of which NRDS datastreams can run on an AMI.
#
#   ./shell/ami/compatibility_report.sh ami-id
#
# For each datastream in infra/aws/terraform/services/nrds/datastreams, it lists the
# images its template runs and whether each one is on:
#   - the given AMI
#   - the AMI the datastream uses now, from prod.tfvars

set -euo pipefail

NEW_AMI_ID=$1
NRDS_DIR="$(cd "$(dirname "$0")/../../infra/aws/terraform/services/nrds" && pwd)"
export AWS_REGION="${AWS_REGION:-us-east-1}"

# Usage: images_on_ami AMI_ID
# Prints the AMI's docker-images tag one image per line, or "unknown".
images_on_ami() {
  images=$(aws ec2 describe-images --image-ids "$1" \
    --query "Images[0].Tags[?Key=='docker-images'].Value | [0]" --output text 2> /dev/null || echo None)
  if [ "$images" = "None" ] || [ -z "$images" ]; then
    echo "unknown"
  else
    echo "$images" | tr ' ' '\n'
  fi
}

# Usage: images_in_template TEMPLATE
images_in_template() {
  {
    grep -o -E 'awiciroh/[a-z0-9_.-]+:[A-Za-z0-9_.-]+' "$1" || true
    grep -o -E 'DS_TAG=[A-Za-z0-9_.-]+' "$1" | sed 's|DS_TAG=|awiciroh/datastream:|' || true
    grep -o -E 'NGIAB_TAG=[A-Za-z0-9_.-]+' "$1" | sed 's|NGIAB_TAG=|awiciroh/ciroh-ngen-image:|' || true
  } | sort -u
}

# Usage: is_on IMAGE IMAGES_ON_AMI
# Prints yes, no or unknown.
is_on() {
  if [ "$2" = "unknown" ]; then
    echo "unknown"
  elif echo "$2" | grep -q -x -F "$1"; then
    echo "yes"
  else
    echo "no"
  fi
}

new_ami_images=$(images_on_ami "$NEW_AMI_ID")
tfvars_lines=""

echo "### Compatibility report for \`$NEW_AMI_ID\`"
echo "| Datastream | Required Images | On \`$NEW_AMI_ID\` | On the current AMI | Compatible |"
echo "|---|---|---|---|---|"

for datastream_dir in "$NRDS_DIR"/datastreams/*/; do
  datastream=$(basename "$datastream_dir")
  ami_variable=$(grep -h -o -E 'variable "[a-z0-9_]+_ami_id"' "$datastream_dir"*.tf | cut -d'"' -f2)
  current_ami_id=$(grep -E "^$ami_variable *=" "$NRDS_DIR/envs/prod.tfvars" | cut -d'"' -f2)
  current_ami_images=$(images_on_ami "$current_ami_id")

  images_column=""
  new_column=""
  current_column=""
  compatible="yes"
  for image in $(images_in_template "$datastream_dir"templates/*.tpl); do
    on_new=$(is_on "$image" "$new_ami_images")
    on_current=$(is_on "$image" "$current_ami_images")
    images_column="$images_column\`$image\`<br>"
    new_column="$new_column$on_new<br>"
    current_column="$current_column$on_current<br>"
    if [ "$on_new" != "yes" ]; then
      compatible="no"
    fi
  done

  echo "| $datastream | ${images_column%<br>} | ${new_column%<br>} | ${current_column%<br>} | $compatible |"
  if [ "$compatible" = "yes" ]; then
    tfvars_lines="$tfvars_lines$ami_variable = \"$NEW_AMI_ID\"
"
  fi
done

echo
if [ -n "$tfvars_lines" ]; then
  echo "To move the compatible datastreams to this AMI, set these in"
  echo "\`infra/aws/terraform/services/nrds/envs/prod.tfvars\` and open a pull request:"
  echo '```hcl'
  printf '%s' "$tfvars_lines"
  echo '```'
else
  echo "No datastream is compatible with this AMI as its template stands."
fi
