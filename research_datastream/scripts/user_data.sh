#!/bin/bash
DS_TAG="latest"
FP_TAG="latest"
NGIAB_TAG="latest"

sudo dnf install git pigz awscli docker -y
sudo systemctl start docker
sudo usermod -aG docker ec2-user
sudo newgrp docker
sg docker -c "
docker pull awiciroh/datastream:$DS_TAG
docker pull awiciroh/forcingprocessor:$FP_TAG
docker pull awiciroh/ciroh-ngen-image:$NGIAB_TAG
docker pull zwills/merkdir:latest
"

cd /home/ec2-user
git clone https://github.com/CIROH-UA/ngen-datastream.git
