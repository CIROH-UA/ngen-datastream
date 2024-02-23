#!/bin/bash

DATASTREAM_PATH="$(eval echo ~$USER)/ngen-datastream"
DATASTREAM_DOCKER="$DATASTREAM_PATH"/docker

cd $DATASTREAM_DOCKER
docker build -t forcingprocessor --no-cache ./forcingprocessor && \
    docker build -t validator --no-cache  ./validator 

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