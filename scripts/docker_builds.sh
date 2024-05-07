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

DATASTREAM_DOCKER="$DATASTREAM_PATH"/docker
cd $DATASTREAM_DOCKER
docker build -t awiciroh/datastream-deps:latest -f Dockerfile.datastream-deps . --no-cache --build-arg TAG_NAME=latest --build-arg ARCH=$(uname -m) --platform linux/$(uname -m) && \
docker build -t awiciroh/forcingprocessor:latest -f Dockerfile.forcingprocessor . --no-cache --build-arg TAG_NAME=latest --platform linux/$(uname -m) && \
    docker build -t awiciroh/datastream:latest -f Dockerfile.datastream . --no-cache --build-arg TAG_NAME=latest --platform linux/$(uname -m)

NGIAB_PATH="$DATASTREAM_PATH"/NGIAB-CloudInfra
NGIAB_DOCKER="$NGIAB_PATH"/docker
git submodule init
git submodule update
cd $NGIAB_DOCKER
docker build -t awiciroh/ngen-deps:latest -f Dockerfile.ngen-deps --no-cache . && \
    docker build -t awiciroh/t-route:latest -f ./Dockerfile.t-route . --no-cache --build-arg TAG_NAME=latest && \
    docker build -t awiciroh/ngen:latest -f ./Dockerfile.ngen . --no-cache --build-arg TAG_NAME=latest && \
    docker build -t awiciroh/ciroh-ngen-image:latest -f ./Dockerfile . --no-cache --build-arg TAG_NAME=latest 

echo "done!"    
