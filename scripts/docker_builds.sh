#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATASTREAM_PATH="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$DATASTREAM_PATH"/docker
DOCKER_DATASTREAM=$DOCKER_DIR/ngen-datastream

PLATFORM=$(uname -m)
PLATORM_TAG=""
if [ $PLATFORM = "x86_64" ]; then
    PLATORM_TAG="-x86"
fi
TAG="latest$PLATORM_TAG"

BUILD="no"
PUSH="no"
while getopts "bp" flag; do
 case $flag in
   b) BUILD="yes"
   ;;
   p) PUSH="yes"
   ;;
   \?)
   ;;
 esac
done

if [ "$BUILD" = "yes" ]; then

  cd $DOCKER_DIR
  echo "Building docker from "$DOCKER_DIR

  docker build -t awiciroh/datastream-deps:$TAG -f Dockerfile.datastream-deps . --no-cache --build-arg TAG_NAME=$TAG --build-arg ARCH=$PLATFORM --platform linux/$PLATFORM

  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf $DOCKER_DATASTREAM
  fi
  mkdir $DOCKER_DATASTREAM
  cp -r $DATASTREAM_PATH/forcingprocessor $DOCKER_DATASTREAM/forcingprocessor
  docker build -t awiciroh/forcingprocessor:$TAG -f Dockerfile.forcingprocessor . --no-cache --build-arg TAG_NAME=$TAG --platform linux/$PLATFORM

  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf $DOCKER_DATASTREAM
  fi
  mkdir $DOCKER_DATASTREAM
  cp -r $DATASTREAM_PATH/python_tools $DOCKER_DATASTREAM/python_tools
  cp -r $DATASTREAM_PATH/configs $DOCKER_DATASTREAM/configs
  docker build -t awiciroh/datastream:$TAG -f Dockerfile.datastream . --no-cache --build-arg TAG_NAME=$TAG --platform linux/$PLATFORM
  echo "Docker containers have been built!"
fi

if [ "$PUSH" = "yes" ]; then
    echo "Pushing docker containers"
    docker push awiciroh/datastream-deps:latest$PLATORM_TAG
    docker push awiciroh/datastream:latest$PLATORM_TAG
    docker push awiciroh/forcingprocessor:latest$PLATORM_TAG
    echo "Docker containers have been pushed to awiciroh dockerhub!"
fi


