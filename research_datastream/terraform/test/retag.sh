#!/bin/bash
set -Eeuo pipefail
# Old tags (override via env: F_OLD, D_OLD, E_OLD if needed)
: "${F_OLD:=latest-arm64}"
: "${D_OLD:=latest-arm64}"
: "${E_OLD:=latest-arm64}"
# Flags → build ordered lists of services to process
services=()    # friendly names (for display)
images=()      # repo/image
olds=()        # old tag for each service
usage() {
  cat <<EOF
Usage:
  $0 [-f] [-d] [-e] <new_tag_for_each_flag_in_order>
Flags:
  -f   forcingprocessor      (awiciroh/forcingprocessor)
  -d   datastream            (awiciroh/datastream)
  -e   datastream-deps       (awiciroh/datastream-deps)
Notes:
- Pass new tags in the SAME ORDER as flags.
- Examples:
    $0 -e 2.2.1-arm64
    $0 -f -d v1.2.0-arm64 v1.1.1-arm64
    $0 -f -d -e v1.2.0-arm64 v1.1.1-arm64 v3.0.0-arm64
- Override old tags via env:
    F_OLD=latest-arm64 D_OLD=latest-arm64 E_OLD=latest-arm64 $0 -f -e v1 v3
EOF
  exit 1
}
while getopts ":fdeh" flag; do
  case "$flag" in
    f) services+=("forcingprocessor"); images+=("awiciroh/forcingprocessor"); olds+=("$F_OLD") ;;
    d) services+=("datastream");       images+=("awiciroh/datastream");       olds+=("$D_OLD") ;;
    e) services+=("datastream-deps");  images+=("awiciroh/datastream-deps");  olds+=("$E_OLD") ;;
    h) usage ;;
    :) echo "Missing value for -$OPTARG"; usage ;;
    \?) echo "Unknown option: -$OPTARG"; usage ;;
  esac
done
shift $((OPTIND-1))
count_flags=${#services[@]}
if (( count_flags == 0 )); then
  echo "Error: choose at least one of -f, -d, -e."
  usage
fi
if (( $# != count_flags )); then
  echo "Error: expected $count_flags new tag(s) in the same order as flags: ${services[*]}"
  usage
fi
retag_and_push() {
  local image="$1" old="$2" new="$3"
  if ! docker image inspect "$image:$old" >/dev/null 2>&1; then
    echo "Error: Local $image:$old not found. Exiting."
    exit 1
  fi
  echo "Retagging $image: $old → $new"
  docker tag "$image:$old" "$image:$new"
  echo "Pushing $image:$new"
  docker push "$image:$new"
}
# Map each provided new tag to the flagged service in order
for i in "${!services[@]}"; do
  new_tag="${1}"; shift
  echo "Processing ${services[$i]}: ${images[$i]} (${olds[$i]} → ${new_tag})"
  retag_and_push "${images[$i]}" "${olds[$i]}" "${new_tag}"
done
echo "Done."
