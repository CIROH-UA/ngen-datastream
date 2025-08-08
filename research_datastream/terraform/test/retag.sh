#!/bin/bash
set -e

while getopts "fed" flag; do
  case $flag in
    f) RETAG_FORCINGPROCESSOR="yes" ;;
    d) RETAG_DATASTREAM="yes" ;;
    \?) echo "Invalid option"; exit 1 ;;
  esac
done

shift $((OPTIND-1))

if [ $# -ne 2 ]; then
    echo "Usage: $0 [-f|-d|-e] <old_tag> <new_tag>"
    echo "  -f : Retag forcingprocessor"
    echo "  -d : Retag datastream"
    echo "  -e : Retag datastream-deps"
    exit 1
fi

OLD_TAG=$1
NEW_TAG=$2

retag_and_push() {
    local image=$1
    echo "Retagging $image from '$OLD_TAG' to '$NEW_TAG'..."
    docker tag "$image:$OLD_TAG" "$image:$NEW_TAG"
    echo "Pushing $image:$NEW_TAG..."
    docker push "$image:$NEW_TAG"
}

if [ "$RETAG_DEPS" = "yes" ]; then
    retag_and_push "awiciroh/datastream-deps"
fi

if [ "$RETAG_FORCINGPROCESSOR" = "yes" ]; then
    retag_and_push "awiciroh/forcingprocessor"
fi

if [ "$RETAG_DATASTREAM" = "yes" ]; then
    retag_and_push "awiciroh/datastream"
fi
