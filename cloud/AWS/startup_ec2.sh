#!/bin/bash
arch=$(dpkg --print-architecture)
echo "Arch: "$arch
curl -L -O https://github.com/LynkerIntel/hfsubset/releases/download/hfsubset-release-12/hfsubset-linux_amd64.tar.gz
curl -L -O https://s3.amazonaws.com/mountpoint-s3-release/latest/x86_64/mount-s3.rpm
sudo dnf update -y
sudo dnf install ./mount-s3.rpm git pip pigz awscli -y
tar -xzvf hfsubset-linux_amd64.tar.gz
rm hfsubset-linux_amd64.tar.gz mount-s3.rpm
sudo mv hfsubset /usr/bin/hfsubset
git clone https://github.com/CIROH-UA/ngen-datastream.git
sudo dnf update
sudo dnf -y install dnf-plugins-core
sudo dnf install docker -y
sudo systemctl start docker
sudo usermod -aG docker ec2-user
sudo newgrp docker
cd ngen-datastream/NGIAB-CloudInfra/
git submodule init
git submodule update
cd docker
docker build -t awiciroh/ngen-deps:latest -f Dockerfile.ngen-deps --no-cache . && docker build -t awiciroh/t-route:latest -f Dockerfile.t-route . --no-cache && docker build -t awiciroh/ngen -f Dockerfile.ngen . --no-cache && docker build -t awiciroh/ciroh-ngen-image:latest-local -f Dockerfile . --no-cache
echo "done!"

