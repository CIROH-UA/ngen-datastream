#!/bin/bash

DOCKERHUB_TOKEN="$(aws secretsmanager get-secret-value --secret-id docker_awiciroh_creds --region us-east-1 --query SecretString --output text | jq -r .DOCKERHUB_TOKEN)"
DOCKERHUB_USERNAME="awiciroh"

if [ "$(echo $DOCKERHUB_TOKEN | docker login -u $DOCKERHUB_USERNAME --password-stdin)" == "Login Succeeded" ]; then             
    echo "Docker login successful"
    /home/ec2-user/ngen-datastream/scripts/docker_builds.sh buildtags -p -t latest-arm64 >> /home/ec2-user/ngen-datastream/docker_build_log.txt
    /home/ec2-user/ngen-datastream/research_datastream/terraform/test/retag.sh buildtags DS_DP_Tag FP_Tag DS_Tag  >> /home/ec2-user/ngen-datastream/docker_build_log.txt
    echo "Push complete"
else
    echo "Docker login failed"
    exit 1
fi

