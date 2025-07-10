#!/bin/bash

DOCKERHUB_TOKEN="$(aws secretsmanager get-secret-value --secret-id docker_awiciroh_creds --region us-east-1 --query SecretString --output text | jq -r .DOCKERHUB_TOKEN)"
DOCKERHUB_USERNAME="awiciroh"

if [ "$(echo $DOCKERHUB_TOKEN | docker login -u $DOCKERHUB_USERNAME --password-stdin)" == "Login Succeeded" ]; then             
    echo "Docker login successful"
    /home/ec2-user/ngen-datastream/scripts/docker_builds.sh -p -t latest-arm64 >> /home/ec2-user/ngen-datastream/docker_build_log.txt
    echo "Push complete"
else
    echo "Docker login failed"
    exit 1
fi

