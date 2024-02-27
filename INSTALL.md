# Install Instructions for ngen-datastream
These steps are [scripted](#scripts) for easy use on Fedora or Amazon Linux distributions.

## Step-by-step
<<<<<<< Updated upstream
1) install packages
=======

1) clone this repository
```
git clone https://github.com/CIROH-UA/ngen-datastream.git
```
2) install packages
>>>>>>> Stashed changes
```
sudo dnf update -y
sudo dnf install git pip pigz awscli
```
2) clone this repository
```
git clone https://github.com/CIROH-UA/ngen-datastream.git
```
3) install docker
```
sudo dnf update -y
sudo dnf install dnf-plugins-core -y
sudo dnf install docker -y
sudo systemctl start docker
sudo usermod -aG docker ec2-user
sudo newgrp docker
```
test with `docker run hello-world`

4) build docker containers
```
cd ~/ngen-datastream/docker && \
docker build -t forcingprocessor --no-cache ./forcingprocessor && \
docker build -t validator --no-cache  ./validator && \
git submodule init && \
git submodule update && \
cd ~/ngen-datastream/NGIAB-CloudInfra/docker && \
docker build -t awiciroh/ngen-deps:latest -f Dockerfile.ngen-deps --no-cache . && \
docker build -t awiciroh/t-route:latest -f ./Dockerfile.t-route . --no-cache --build-arg TAG_NAME=latest && \
docker build -t awiciroh/ngen:latest -f ./Dockerfile.ngen . --no-cache --build-arg TAG_NAME=latest && \
docker build -t awiciroh/ciroh-ngen-image:latest -f ./Dockerfile . --no-cache --build-arg TAG_NAME=latest 
```

4) install hfsubset, this is required if you intend to use the subsetting feature
```
curl -L -O https://github.com/LynkerIntel/hfsubset/releases/download/hfsubset-release-12/hfsubset-linux_amd64.tar.gz
tar -xzvf hfsubset-linux_amd64.tar.gz
rm hfsubset-linux_amd64.tar.gz
sudo mv hfsubset /usr/bin/hfsubset
```
5) install mount-s3, this is required if you instend to mount a s3 bucket as an output for the datastream
```
curl -L -O https://s3.amazonaws.com/mountpoint-s3-release/latest/x86_64/mount-s3.rpm
sudo dnf install ./mount-s3.rpm
rm mount-s3.rpm
```
You're ready to run ngen-datastream!

## Scripts

ngen-datastream was designed on Fedora and Amazon Linux. These instructions assuming starting from a freshly launched host.

1) Create a shell script that will execute the install instructions. This will install the datastream, related packages, and docker.
```
vi ./startup.sh
```
2) Copy the contents of this [file](https://github.com/CIROH-UA/ngen-datastream/blob/main/scripts/startup_ec2.sh). `:wq` to save and close the file.
Change permissions and execute the startup script
```
chmod +700 ./startup.sh && ./startup.sh
```
3) Exit the session and log back in to ensure docker daemon is running.

4) Run the docker builds script
```
./ngen-datastream/scripts/docker_builds.sh
```

## AWS
If you intended to interact with AWS via the datastream. Remember to configure AWS credentials on the host appropriately via `aws configure`.
