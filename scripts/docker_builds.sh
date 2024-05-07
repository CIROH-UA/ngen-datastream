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

NGIAB_PATH="$DATASTREAM_PATH"/NGIAB-CloudInfra
NGIAB_DOCKER="$NGIAB_PATH"/docker
git submodule init
git submodule update
cd $NGIAB_DOCKER
docker build -t awiciroh/ngen-deps:$TAG -f Dockerfile.ngen-deps --no-cache . && \
    docker build -t awiciroh/t-route:$TAG -f ./Dockerfile.t-route . --no-cache --build-arg TAG_NAME=$TAG && \
    docker build -t awiciroh/ngen:$TAG-f ./Dockerfile.ngen . --no-cache --build-arg TAG_NAME=$TAG && \
    docker build -t awiciroh/ciroh-ngen-image:$TAG -f ./Dockerfile . --no-cache --build-arg TAG_NAME=$TAG

echo "done!"    
