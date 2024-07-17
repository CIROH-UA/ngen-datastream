#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATASTREAM_PATH="$(dirname "$SCRIPT_DIR")"       
PLATFORM=$(uname -m)
PLATORM_TAG=""
if [ $PLATFORM = "x86_64" ]; then
    PLATORM_TAG="-x86"
fi
DOCKER_PUSH="no"
while getopts "p:" opt; do
  case $opt in
    p)
      DOCKER_PUSH=$OPTARG
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      exit 1
      ;;
  esac
done
TAG="latest$PLATORM_TAG"
DATASTREAM_DOCKER="$DATASTREAM_PATH"/docker_local
cd $DATASTREAM_DOCKER
echo "Building docker from "$DATASTREAM_DOCKER
docker build -t awiciroh/datastream-deps:$TAG -f Dockerfile.datastream-deps . --no-cache --build-arg TAG_NAME=$TAG --build-arg ARCH=$PLATFORM --platform linux/$PLATFORM 
docker build -t awiciroh/forcingprocessor:$TAG -f Dockerfile.forcingprocessor . --no-cache --build-arg TAG_NAME=$TAG --platform linux/$PLATFORM
docker build -t awiciroh/datastream:$TAG -f Dockerfile.datastream . --no-cache --build-arg TAG_NAME=$TAG --platform linux/$PLATFORM

if [ "$DOCKER_PUSH" = "yes" ]; then
    echo "Pushing docker containers"
    docker push awiciroh/datastream-deps:latest-x86
    docker push awiciroh/datastream:latest-x86
    docker push awiciroh/forcingprocessor:latest-x86
fi

echo "done!"    
