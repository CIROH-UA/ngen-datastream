#!/bin/bash
set -e

# Fixed old tags (change here if needed)
F_OLD="latest-arm64"
D_OLD="latest-arm64"

# Flags
RETAG_F=""
RETAG_D=""

while getopts "fd" flag; do
  case $flag in
    f) RETAG_F="yes" ;;
    d) RETAG_D="yes" ;;
  esac
done
shift $((OPTIND-1))

# Expect two args: new tag for forcingprocessor, new tag for datastream
if [ $# -ne 2 ]; then
  echo "Usage: $0 [-f] [-d] <f_new_tag> <d_new_tag>"
  exit 1
fi

F_NEW=$1
D_NEW=$2

retag_and_push() {
  local image=$1 old=$2 new=$3
  docker tag "$image:$old" "$image:$new"
  docker push "$image:$new"
}

if [ "$RETAG_F" = "yes" ]; then
  retag_and_push "awiciroh/forcingprocessor" "$F_OLD" "$F_NEW"
fi

if [ "$RETAG_D" = "yes" ]; then
  retag_and_push "awiciroh/datastream" "$D_OLD" "$D_NEW"
fi
# ./retag.sh -f -d v1.2.0 v2.3.0
