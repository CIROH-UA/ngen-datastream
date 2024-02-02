#!/bin/bash
sudo apt update -y
sudo apt-get update -y
sudo apt install git pigz awscli -y
git clone https://github.com/CIROH-UA/ngen-datastream.git
curl -L -O https://github.com/LynkerIntel/hfsubset/releases/download/hfsubset-release-12/hfsubset-linux_amd64.tar.gz
tar -xzvf hfsubset-linux_amd64.tar.gz
sudo mv hfsubset /usr/bin/hfsubset
aws configure
mkdir docker
aws s3 sync s3://ngen-datastream/docker/docker ~/docker
sudo apt-get update -y
sudo apt-get install ca-certificates curl gnupg -y
sudo install -m 0755 -d /etc/apt/keyrings -y
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg 
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo   "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" |   sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker ${USER}

echo "log out and back in"

#!/bin/bash
cd docker
sudo docker build -t awiciroh/ngen-deps:latest -f Dockerfile.ngen-deps --no-cache . && docker build -t awiciroh/t-route:latest -f Dockerfile.t-route . --no-cache && docker build -t awiciroh/ngen -f Dockerfile.ngen . --no-cache && docker build -t awiciroh/ciroh-ngen-image:latest-local -f Dockerfile . --no-cache