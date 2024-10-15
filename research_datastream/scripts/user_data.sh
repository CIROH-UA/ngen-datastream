#!/bin/bash
ARCH_TAG="-x86"
if [ "$(uname -m)" == 'aarch64' ];then
    ARCH_TAG=""
fi
sudo dnf install git -y
cd /home/ec2-user
runuser -l ec2-user -c 'git clone https://github.com/CIROH-UA/ngen-datastream.git'
runuser -l ec2-user -c 'curl -L -O https://github.com/lynker-spatial/hfsubsetCLI/releases/download/v1.1.0/hfsubset-v1.1.0-linux_arm64.tar.gz'
runuser -l ec2-user -c 'tar -xzvf hfsubset-v1.1.0-linux_arm64.tar.gz'
runuser -l ec2-user -c 'sudo mv ./hfsubset /usr/bin/hfsubset'
runuser -l ec2-user -c 'sudo dnf install pip pigz awscli -y'
runuser -l ec2-user -c 'sudo dnf install docker -y'
runuser -l ec2-user -c 'sudo systemctl start docker'
runuser -l ec2-user -c 'sudo usermod -aG docker ec2-user'
runuser -l ec2-user -c 'sudo newgrp docker'
docker pull awiciroh/datastream:latest$ARCH_TAG
docker pull awiciroh/forcingprocessor:latest$ARCH_TAG
docker pull awiciroh/ciroh-ngen-image:1.2.1$ARCH_TAG
docker pull zwills/merkdir