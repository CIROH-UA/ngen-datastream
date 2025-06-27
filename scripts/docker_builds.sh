#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATASTREAM_PATH="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$DATASTREAM_PATH"/docker
DOCKER_DATASTREAM=$DOCKER_DIR/ngen-datastream

TAG="latest"
PLATFORMS="linux/amd64,linux/arm64"

BUILD_FORCINGPROCESSOR="no"
BUILD_DATASTREAM="no"
PUSH="no"
BUILD_DEPS="no"
while getopts "pefd" flag; do
 case $flag in
   p) PUSH="yes"
   ;;
   e) BUILD_DEPS="yes"
   ;; 
   f) BUILD_FORCINGPROCESSOR="yes"
   ;; 
   d) BUILD_DATASTREAM="yes"
   ;;         
   \?)
   ;;
 esac
done

cd $DOCKER_DIR

if ! docker buildx ls | grep -q 'multi-builder'; then
  docker buildx create --name multi-builder --use
else
  docker buildx use multi-builder
fi

if [ "$BUILD_DEPS" = "yes" ]; then
  docker buildx build --platform $PLATFORMS -t awiciroh/datastream-deps:$TAG -f Dockerfile.datastream-deps . --no-cache --build-arg ARCH=multi --push=$([ "$PUSH" = "yes" ] && echo true || echo false)
  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf $DOCKER_DATASTREAM
  fi
fi

if [ "$BUILD_FORCINGPROCESSOR" = "yes" ]; then
  mkdir $DOCKER_DATASTREAM
  cp -r $DATASTREAM_PATH/forcingprocessor $DOCKER_DATASTREAM/forcingprocessor
  docker buildx build --platform $PLATFORMS -t awiciroh/forcingprocessor:$TAG -f Dockerfile.forcingprocessor . --no-cache --build-arg TAG_NAME=$TAG --push=$([ "$PUSH" = "yes" ] && echo true || echo false)
  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf $DOCKER_DATASTREAM
  fi
fi

if [ "$BUILD_DATASTREAM" = "yes" ]; then
  mkdir $DOCKER_DATASTREAM
  cp -r $DATASTREAM_PATH/python_tools $DOCKER_DATASTREAM/python_tools
  cp -r $DATASTREAM_PATH/configs $DOCKER_DATASTREAM/configs
  docker buildx build --platform $PLATFORMS -t awiciroh/datastream:$TAG -f Dockerfile.datastream . --no-cache --build-arg TAG_NAME=$TAG --push=$([ "$PUSH" = "yes" ] && echo true || echo false)
  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf $DOCKER_DATASTREAM
  fi
fi

if [ "$PUSH" = "yes" ]; then
    echo "Docker containers have been pushed to awiciroh dockerhub!"
else
    echo "Build complete. Use -p to push images to Docker Hub."
fi