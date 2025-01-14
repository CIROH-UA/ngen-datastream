#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATASTREAM_PATH="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$DATASTREAM_PATH"/docker
DOCKER_DATASTREAM=$DOCKER_DIR/ngen-datastream

BUILD_FORCINGPROCESSOR="no"
BUILD_DATASTREAM="no"
BUILD_DEPS="no"
TAG="tmp"
PUSH_LOAD="--load"
while getopts "pefdt:" flag; do
  case $flag in
    e) BUILD_DEPS="yes"
    ;;
    f) BUILD_FORCINGPROCESSOR="yes"
    ;;
    d) BUILD_DATASTREAM="yes"
    ;;
    p) PUSH_LOAD="--push"
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
echo "BUILD_DATASTREAM "$BUILD_DATASTREAM
echo "PUSH_LOAD" $PUSH_LOAD
echo "TAG "$TAG

cd $DOCKER_DIR
if [ "$BUILD_DEPS" = "yes" ]; then
  docker buildx build -t awiciroh/datastream-deps:$TAG -f Dockerfile.datastream-deps . --no-cache --platform linux/amd64,linux/arm64 $PUSH_LOAD
  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf $DOCKER_DATASTREAM
  fi
fi
if [ "$BUILD_FORCINGPROCESSOR" = "yes" ]; then
  mkdir $DOCKER_DATASTREAM
  cp -r $DATASTREAM_PATH/forcingprocessor $DOCKER_DATASTREAM/forcingprocessor
  docker buildx build -t awiciroh/forcingprocessor:$TAG -f Dockerfile.forcingprocessor . --no-cache --build-arg TAG=$TAG --platform linux/amd64,linux/arm64 $PUSH_LOAD
  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf $DOCKER_DATASTREAM
  fi
fi
if [ "$BUILD_DATASTREAM" = "yes" ]; then
  mkdir $DOCKER_DATASTREAM
  cp -r $DATASTREAM_PATH/python_tools $DOCKER_DATASTREAM/python_tools
  cp -r $DATASTREAM_PATH/configs $DOCKER_DATASTREAM/configs

  docker buildx build -t awiciroh/datastream:$TAG -f Dockerfile.datastream . --no-cache --build-arg TAG=$TAG --platform linux/amd64,linux/arm64 $PUSH_LOAD
  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf $DOCKER_DATASTREAM
  fi
fi


