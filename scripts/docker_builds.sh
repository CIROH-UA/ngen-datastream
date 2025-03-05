#!/bin/bash -x
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATASTREAM_PATH="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$DATASTREAM_PATH"/docker
DOCKER_DATASTREAM=$DOCKER_DIR/ngen-datastream

BUILD_FORCINGPROCESSOR="no"
BUILD_DATASTREAM="no"
BUILD_DEPS="no"
TAG="tmp"
PUSH_LOAD="--load"
PLATFORM="linux/amd64,linux/arm64"
REPO=""
while getopts "pefdm:t:" flag; do
  case $flag in
    e) BUILD_DEPS="yes"
    ;;
    f) BUILD_FORCINGPROCESSOR="yes"
    ;;
    d) BUILD_DATASTREAM="yes"
    ;;
    p) PUSH_LOAD="--push"
    ;;
    m) PLATFORM="$OPTARG"
    ;;     
    t) TAG="$OPTARG"
    ;;
    \?)
    echo "Invalid option: -$OPTARG" >&2
    ;;
  esac
done

echo "BUILD_DEPS "$BUILD_DEPS
echo "BUILD_FORCINGPROCESSOR "$BUILD_FORCINGPROCESSOR
echo "BUILD_DATASTREAM "$BUILD_DATASTREAM
echo "PUSH_LOAD" $PUSH_LOAD
echo "PLATFORM "$PLATFORM
echo "TAG "$TAG
echo "REPO "$REPO

cd $DOCKER_DIR
if [ "$BUILD_DEPS" = "yes" ]; then
  docker buildx build -t awiciroh/datastream-deps:$TAG -f Dockerfile.datastream-deps . --platform $PLATFORM --push
  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf $DOCKER_DATASTREAM
  fi
fi
if [ "$BUILD_FORCINGPROCESSOR" = "yes" ]; then
  mkdir $DOCKER_DATASTREAM
  cp -r $DATASTREAM_PATH/forcingprocessor $DOCKER_DATASTREAM/forcingprocessor
  docker buildx build -t awiciroh/forcingprocessor:$TAG -f Dockerfile.forcingprocessor . --build-arg TAG="$TAG" --platform $PLATFORM $PUSH_LOAD
  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf $DOCKER_DATASTREAM
  fi
fi
if [ "$BUILD_DATASTREAM" = "yes" ]; then
  mkdir $DOCKER_DATASTREAM
  cp -r $DATASTREAM_PATH/python_tools $DOCKER_DATASTREAM/python_tools
  cp -r $DATASTREAM_PATH/configs $DOCKER_DATASTREAM/configs

  docker buildx build -t awiciroh/datastream:$TAG -f Dockerfile.datastream . --build-arg TAG="$TAG" --platform $PLATFORM $PUSH_LOAD
  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf $DOCKER_DATASTREAM
  fi
fi


