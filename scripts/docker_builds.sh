#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATASTREAM_PATH="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$DATASTREAM_PATH"/docker
DOCKER_DATASTREAM=$DOCKER_DIR/ngen-datastream

PLATFORM=$(uname -m)
TAG="latest"

BUILD_FORCINGPROCESSOR="no"
BUILD_DATASTREAM="no"
PUSH="no"
BUILD_DEPS="no"
while getopts "pefdt:" flag; do
 case $flag in
   p) PUSH="yes"
   ;;
   e) BUILD_DEPS="yes"
   ;;
   f) BUILD_FORCINGPROCESSOR="yes"
   ;;
   d) BUILD_DATASTREAM="yes"
   ;;
   t) TAG="$OPTARG"
   ;;
   \?)
   ;;
 esac
done

cd $DOCKER_DIR
if [ "$BUILD_DEPS" = "yes" ]; then
  docker build -t awiciroh/datastream-deps:$TAG -f Dockerfile.datastream-deps . --no-cache --build-arg ARCH=$PLATFORM
  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf $DOCKER_DATASTREAM
  fi
fi
if [ "$BUILD_FORCINGPROCESSOR" = "yes" ]; then
  mkdir $DOCKER_DATASTREAM
  cp -r $DATASTREAM_PATH/forcingprocessor $DOCKER_DATASTREAM/forcingprocessor
  docker build -t awiciroh/forcingprocessor:$TAG -f Dockerfile.forcingprocessor . --no-cache --build-arg TAG_NAME=$TAG
  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf $DOCKER_DATASTREAM
  fi
fi
if [ "$BUILD_DATASTREAM" = "yes" ]; then
  mkdir $DOCKER_DATASTREAM
  cp -r $DATASTREAM_PATH/python_tools $DOCKER_DATASTREAM/python_tools
  cp -r $DATASTREAM_PATH/configs $DOCKER_DATASTREAM/configs
  docker build -t awiciroh/datastream:$TAG -f Dockerfile.datastream . --no-cache --build-arg TAG_NAME=$TAG
  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf $DOCKER_DATASTREAM
  fi
fi

if [ "$PUSH" = "yes" ]; then
    echo "Pushing docker containers"
    if [ "$SKIP_DEPS" = "no" ]; then
      docker push awiciroh/datastream-deps:$TAG
    fi
    docker push awiciroh/datastream-deps:$TAG
    docker push awiciroh/datastream:$TAG
    docker push awiciroh/forcingprocessor:$TAG
    echo "Docker containers have been pushed to awiciroh dockerhub!"
fi
