#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATASTREAM_PATH="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$DATASTREAM_PATH"/docker
DOCKER_DATASTREAM=$DOCKER_DIR/ngen-datastream
PLATFORM=$(uname -m)
TAG="latest"

cleanup_docker_datastream() {
  if [ -d "$DOCKER_DATASTREAM" ]; then
    rm -rf "$DOCKER_DATASTREAM"
  fi
}

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
   a) BUILD_ALL="yes"
   ;;
   t) TAG="$OPTARG"
   ;;
   \?)
   ;;
 esac
done
echo "Using TAG: $TAG"
cd "$DOCKER_DIR"

if [ "$BUILD_DEPS" = "yes" ]; then
  echo "Building datastream-deps:$TAG"
  docker build -t awiciroh/datastream-deps:$TAG \
               -f Dockerfile.datastream-deps . --no-cache --build-arg ARCH=$PLATFORM
  cleanup_docker_datastream
fi

if [ "$BUILD_FORCINGPROCESSOR" = "yes" ]; then
  echo "Building forcingprocessor:$TAG"
  mkdir "$DOCKER_DATASTREAM"
  cp -r "$DATASTREAM_PATH"/forcingprocessor "$DOCKER_DATASTREAM"/forcingprocessor
  docker build -t awiciroh/forcingprocessor:$TAG \
               -f Dockerfile.forcingprocessor . --no-cache --build-arg TAG_NAME=$TAG
  cleanup_docker_datastream
fi

if [ "$BUILD_DATASTREAM" = "yes" ]; then
  echo "Building datastream:$TAG"
  mkdir "$DOCKER_DATASTREAM"
  cp -r "$DATASTREAM_PATH"/python_tools "$DOCKER_DATASTREAM"/python_tools
  cp -r "$DATASTREAM_PATH"/configs "$DOCKER_DATASTREAM"/configs
  docker build -t awiciroh/datastream:$TAG \
               -f Dockerfile.datastream . --no-cache --build-arg TAG_NAME=$TAG
  cleanup_docker_datastream
fi

if [ "$PUSH" = "yes" ]; then
    echo "Pushing docker containers"
    
    # Only push what was actually built
    if [ "$BUILD_DEPS" = "yes" ]; then
      echo "Pushing datastream-deps"
      docker push awiciroh/datastream-deps:$TAG
    fi
    
    if [ "$BUILD_FORCINGPROCESSOR" = "yes" ]; then
      echo "Pushing forcingprocessor"
      docker push awiciroh/forcingprocessor:$TAG
    fi
    
    if [ "$BUILD_DATASTREAM" = "yes" ]; then
      echo "Pushing datastream"
      docker push awiciroh/datastream:$TAG
    fi

    if [ "$BUILD_ALL" = "yes" ]; then
      echo "Pushing all the services"
      docker push awiciroh/datastream-deps:$TAG
      docker push awiciroh/forcingprocessor:$TAG
      docker push awiciroh/datastream:$TAG
    fi
    echo "Docker containers have been pushed to awiciroh dockerhub!"
fi