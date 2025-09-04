#!/bin/bash

# Log file location
LOG_FILE="/home/ec2-user/ngen-datastream/docker_build_log.txt"

# Accept tag as command line argument, default to "latest-arm64" if not provided
TAG="${1:-latest-arm64}"
BUILD_ARGS="${2:-}"

echo "Script called with TAG: $TAG, BUILD_ARGS: $BUILD_ARGS" | tee -a "$LOG_FILE"

DOCKERHUB_TOKEN="$(aws secretsmanager get-secret-value --secret-id docker_awiciroh_creds --region us-east-1 --query SecretString --output text | jq -r .DOCKERHUB_TOKEN)"
DOCKERHUB_USERNAME="awiciroh"

# Parse BUILD_ARGS to determine what to push
PUSH_DEPS="no"
PUSH_FP="no"
PUSH_DS="no"

if [ -n "$BUILD_ARGS" ]; then
    # Clean up BUILD_ARGS (remove quotes if present)
    BUILD_ARGS_CLEAN=$(echo "$BUILD_ARGS" | sed 's/^"//;s/"$//')
    echo "Processing build arguments: $BUILD_ARGS_CLEAN" | tee -a "$LOG_FILE"
    
    # Check what services to push based on build flags
    if [[ "$BUILD_ARGS_CLEAN" == *"-e"* ]]; then
        PUSH_DEPS="yes"
        echo "Will push datastream-deps" | tee -a "$LOG_FILE"
    fi
    
    if [[ "$BUILD_ARGS_CLEAN" == *"-f"* ]]; then
        PUSH_FP="yes"
        echo "Will push forcingprocessor" | tee -a "$LOG_FILE"
    fi
    
    if [[ "$BUILD_ARGS_CLEAN" == *"-d"* ]]; then
        PUSH_DS="yes"
        echo "Will push datastream" | tee -a "$LOG_FILE"
    fi
else
    echo "No BUILD_ARGS provided - nothing to push" | tee -a "$LOG_FILE"
    exit 0
fi

if echo "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin; then             
    echo "Docker login successful" | tee -a "$LOG_FILE"
    echo "Retagging and pushing images with tag: $TAG" | tee -a "$LOG_FILE"
    
    # Only retag and push services that were built (based on BUILD_ARGS)
    if [ "$PUSH_DEPS" = "yes" ]; then
        echo "Retagging and pushing datastream-deps" | tee -a "$LOG_FILE"
        docker tag awiciroh/datastream-deps:latest-arm64 awiciroh/datastream-deps:$TAG 2>&1 | tee -a "$LOG_FILE"
        docker push awiciroh/datastream-deps:$TAG 2>&1 | tee -a "$LOG_FILE"
        docker push awiciroh/datastream-deps:latest-arm64 2>&1 | tee -a "$LOG_FILE"
    fi
    
    if [ "$PUSH_FP" = "yes" ]; then
        echo "Retagging and pushing forcingprocessor" | tee -a "$LOG_FILE"
        docker tag awiciroh/forcingprocessor:latest-arm64 awiciroh/forcingprocessor:$TAG 2>&1 | tee -a "$LOG_FILE"
        docker push awiciroh/forcingprocessor:$TAG 2>&1 | tee -a "$LOG_FILE"
        docker push awiciroh/forcingprocessor:latest-arm64 2>&1 | tee -a "$LOG_FILE"
    fi
    
    if [ "$PUSH_DS" = "yes" ]; then
        echo "Retagging and pushing datastream" | tee -a "$LOG_FILE"
        docker tag awiciroh/datastream:latest-arm64 awiciroh/datastream:$TAG 2>&1 | tee -a "$LOG_FILE"
        docker push awiciroh/datastream:$TAG 2>&1 | tee -a "$LOG_FILE"
        docker push awiciroh/datastream:latest-arm64 2>&1 | tee -a "$LOG_FILE"
    fi
    
    echo "Retagging and pushing completed" | tee -a "$LOG_FILE"
    
else
    echo "Docker login failed" | tee -a "$LOG_FILE"
    exit 1
fi
