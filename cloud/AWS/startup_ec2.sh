#!/bin/bash
sudo dnf update -y
sudo dnf install git pip pigz awscli -y
curl -L -O https://github.com/LynkerIntel/hfsubset/releases/download/hfsubset-release-12/hfsubset-linux_amd64.tar.gz
tar -xzvf hfsubset-linux_amd64.tar.gz
sudo mv hfsubset /usr/bin/hfsubset
git clone https://github.com/CIROH-UA/ngen-datastream.git
python3 -m pip install --upgrade pip
pip3 install -r /home/ec2-user/ngen-datastream/python/requirements.txt --no-cache
aws configure
aws configure set s3.max_concurrent_requests 256
mkdir docker
aws s3 sync s3://ngen-datastream/docker/docker ~/docker
sudo dnf update
sudo dnf -y install dnf-plugins-core
sudo dnf install docker -y
sudo systemctl start docker
sudo usermod -aG docker ${USER}
curl -L -O https://s3.amazonaws.com/mountpoint-s3-release/latest/x86_64/mount-s3.rpm
sudo yum install -y ./mount-s3.rpm
echo "cd docker && sudo docker build -t awiciroh/ngen-deps:latest -f Dockerfile.ngen-deps --no-cache . && docker build -t awiciroh/t-route:latest -f Dockerfile.t-route . --no-cache && docker build -t awiciroh/ngen -f Dockerfile.ngen . --no-cache && docker build -t awiciroh/ciroh-ngen-image:latest-local -f Dockerfile . --no-cache"
echo "copy that ^^ and log out of session, log back in and run that command"

