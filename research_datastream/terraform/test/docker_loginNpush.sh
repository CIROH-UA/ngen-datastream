#!/bin/bash

# Accept tag as command line argument, default to "latest-arm64" if not provided
TAG="${1:-latest-arm64}"

DOCKERHUB_TOKEN="$(aws secretsmanager get-secret-value --secret-id docker_awiciroh_creds --region us-east-1 --query SecretString --output text | jq -r .DOCKERHUB_TOKEN)"
DOCKERHUB_USERNAME="awiciroh"

if [ "$(echo $DOCKERHUB_TOKEN | docker login -u $DOCKERHUB_USERNAME --password-stdin)" == "Login Succeeded" ]; then             
    echo "Docker login successful"    
    echo "Retagging and pushing images with tag: $TAG"
    # Retag and push datastream-deps
    docker tag awiciroh/datastream-deps:latest-arm64 awiciroh/datastream-deps:$TAG
    # Retag and push datastream
    docker tag awiciroh/datastream:latest-arm64 awiciroh/datastream:$TAG
    # Retag and push forcingprocessor
    docker tag awiciroh/forcingprocessor:latest-arm64 awiciroh/forcingprocessor:$TAG

    /home/ec2-user/ngen-datastream/scripts/docker_builds.sh $BUILD_ARGS -p -t $TAG >> /home/ec2-user/ngen-datastream/docker_build_log.txt
else
    echo "Docker login failed"
    exit 1
fi
