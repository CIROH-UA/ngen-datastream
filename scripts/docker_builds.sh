#!/bin/bash
usage() {
    echo ""
    echo "Usage: $0 [options]"
    echo "  -d, --DATASTREAM_PATH  <Path to ngen-datastream> "  
}
DATASTREAM_PATH=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        -d|--DATASTREAM_PATH) DATASTREAM_PATH="$2"; shift 2;;
        -p|--PUSH_DOCKERHUB) PUSH_DOCKERHUB="$2"; shift 2;;
        *) usage;;
    esac
done        
PLATFORM=$(uname -m)
PLATORM_TAG=""
if [ $PLATFORM = "x86_64" ]; then
    PLATORM_TAG="-x86"
fi
TAG="latest$PLATORM_TAG"
DATASTREAM_DOCKER="$DATASTREAM_PATH"/docker
cd $DATASTREAM_DOCKER
docker build -t awiciroh/datastream-deps:$TAG -f Dockerfile.datastream-deps . --no-cache --build-arg TAG_NAME=$TAG --build-arg ARCH=$PLATFORM --platform linux/$PLATFORM 
docker build -t awiciroh/forcingprocessor:$TAG -f Dockerfile.forcingprocessor . --no-cache --build-arg TAG_NAME=$TAG --platform linux/$PLATFORM
docker build -t awiciroh/datastream:$TAG -f Dockerfile.datastream . --no-cache --build-arg TAG_NAME=$TAG --platform linux/$PLATFORM

if [ -z $PUSH_DOCKERHUB ]; then
    docker push awiciroh/datastream-deps:latest-x86
    docker push awiciroh/datastream:latest-x86
    docker push awiciroh/forcingprocessor:latest-x86
fi

echo "done!"    
