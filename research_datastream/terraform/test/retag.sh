#!/bin/bash
set -e

# Fixed old tags (change here if needed)
F_OLD="latest-arm64"
D_OLD="latest-arm64"
E_OLD="latest-arm64"  # datastream-deps old tag

# Flags
RETAG_F=""
RETAG_D=""
RETAG_E=""  # datastream-deps flag

while getopts "fde" flag; do
  case $flag in
    f) RETAG_F="yes" ;;
    d) RETAG_D="yes" ;;
    e) RETAG_E="yes" ;;  # datastream-deps option
  esac
done

shift $((OPTIND-1))

# Expect three args: new tag for forcingprocessor, new tag for datastream, new tag for datastream-deps
if [ $# -ne 3 ]; then
  echo "Usage: $0 [-f] [-d] [-e] <f_new_tag> <d_new_tag> <e_new_tag>"
  exit 1
fi

F_NEW=$1
D_NEW=$2
E_NEW=$3  # datastream-deps new tag

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

if [ "$RETAG_E" = "yes" ]; then
  retag_and_push "awiciroh/datastream-deps" "$E_OLD" "$E_NEW"
fi
