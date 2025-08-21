#!/bin/bash

# Accept tag as command line argument, default to "latest-arm64" if not provided
TAG="${1:-latest-arm64}"
BUILD_ARGS="${2:-}"

echo "Script called with TAG: $TAG, BUILD_ARGS: $BUILD_ARGS"

DOCKERHUB_TOKEN="$(aws secretsmanager get-secret-value --secret-id docker_awiciroh_creds --region us-east-1 --query SecretString --output text | jq -r .DOCKERHUB_TOKEN)"
DOCKERHUB_USERNAME="awiciroh"

# Parse BUILD_ARGS to determine what to push
PUSH_DEPS="no"
PUSH_FP="no"
PUSH_DS="no"

if [ -n "$BUILD_ARGS" ]; then
    # Clean up BUILD_ARGS (remove quotes if present)
    BUILD_ARGS_CLEAN=$(echo "$BUILD_ARGS" | sed 's/^"//;s/"$//')
    echo "Processing build arguments: $BUILD_ARGS_CLEAN"
    
    # Check what services to push based on build flags
    if [[ "$BUILD_ARGS_CLEAN" == *"-e"* ]]; then
        PUSH_DEPS="yes"
        echo "Will push datastream-deps"
    fi
    
    if [[ "$BUILD_ARGS_CLEAN" == *"-f"* ]]; then
        PUSH_FP="yes"
        echo "Will push forcingprocessor"
    fi
    
    if [[ "$BUILD_ARGS_CLEAN" == *"-d"* ]]; then
        PUSH_DS="yes"
        echo "Will push datastream"
    fi
else
    echo "No BUILD_ARGS provided - nothing to push"
    exit 0
fi

# Fixed login check
if echo "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin; then             
    echo "Docker login successful"
    docker images
    echo "Retagging and pushing images with tag: $TAG"
    
    # Only retag and push services that were built (based on BUILD_ARGS)
    if [ "$PUSH_DEPS" = "yes" ]; then
        echo "Retagging and pushing datastream-deps"
        docker tag awiciroh/datastream-deps:latest-arm64 awiciroh/datastream-deps:$TAG
        docker push awiciroh/datastream-deps:$TAG
    fi
    
    if [ "$PUSH_FP" = "yes" ]; then
        echo "Retagging and pushing forcingprocessor"
        docker tag awiciroh/forcingprocessor:latest-arm64 awiciroh/forcingprocessor:$TAG
        docker push awiciroh/forcingprocessor:$TAG
    fi
    
    if [ "$PUSH_DS" = "yes" ]; then
        echo "Retagging and pushing datastream"
        docker tag awiciroh/datastream:latest-arm64 awiciroh/datastream:$TAG
        docker push awiciroh/datastream:$TAG
    fi
    
    # Show what we have after operations
    docker images
    
    echo "Retagging and pushing completed"
    
else
    echo "Docker login failed"
    exit 1
fi
