# Install Instructions for ngen-datastream
These steps are provided [scripted](#scripts) or [step-by-step](#step-by-step). Note some steps are specific to either `x86` or `aarch64`

## Prerequisites
* Linux OS
* Docker

These instructions assume launching an instance from a blank Amazon 2023 Linux image. Steps may vary depending on your specific linux distribution.

## Scripted
1) Create a shell script that will execute the install instructions. This will install the datastream and required packages.
```
vi ./install.sh
```
2) Copy the contents of this [file](https://github.com/CIROH-UA/ngen-datastream/blob/main/scripts/install.sh). `:wq` to save and close the file.
Change permissions and execute the startup script
```
chmod +700 ./install.sh && ./install.sh
```
4) Run the docker builds script
```
./ngen-datastream/scripts/docker_builds.sh -d <path to ngen-datastream directory>
```
`aws_configure` if you intend to mount an s3 bucket or reference a bucket in the configuration.

You're ready to run ngen-datastream!

## Step-by-step 
`$USER=($whomami)`

For `x86`, `PKG_MNGR="dnf"`

For `aarch64`, `PKG_MNGR="yum"`

1) Update package manager and install packages
```
sudo $PKG_MNGR update -y
sudo $PKG_MNGR install git pip python pigz awscli -y
```
`x86` : `sudo $PKG_MNGR update -y
sudo $PKG_MNGR install dnf-plugins-core -y`

2) install packages from internet

`x86` : `curl -L -O https://s3.amazonaws.com/mountpoint-s3-release/latest/x86_64/mount-s3.rpm` 

`aarch64` : `curl -L -O https://s3.amazonaws.com/mountpoint-s3-release/latest/arm64/mount-s3.rpm`
```
sudo dnf update -y
sudo dnf ./mount-s3.rpm
```
3) clone this repository
```
git clone https://github.com/CIROH-UA/ngen-datastream.git
```
4) build docker containers
```
cd ./ngen-datastream/docker
docker build -t datastream-deps:latest -f Dockerfile.datastream-deps . --no-cache --build-arg TAG_NAME=latest --build-arg ARCH=$(uname -m) && \
docker build -t forcingprocessor:latest -f Dockerfile.forcingprocessor . --no-cache --build-arg TAG_NAME=latest && \
    docker build -t datastream:latest -f Dockerfile.datastream . --no-cache --build-arg TAG_NAME=latest 

git submodule init
git submodule update
cd ./ngen-datastream/NGIAB-CloudInfra/docker
docker build -t awiciroh/ngen-deps:latest -f Dockerfile.ngen-deps --no-cache . && \
    docker build -t awiciroh/t-route:latest -f ./Dockerfile.t-route . --no-cache --build-arg TAG_NAME=latest && \
    docker build -t awiciroh/ngen:latest -f ./Dockerfile.ngen . --no-cache --build-arg TAG_NAME=latest && \
    docker build -t awiciroh/ciroh-ngen-image:latest -f ./Dockerfile . --no-cache --build-arg TAG_NAME=latest 
```

`aws_configure` if you intend to mount an s3 bucket or reference a bucket in the configuration.

You're ready to run ngen-datastream!

