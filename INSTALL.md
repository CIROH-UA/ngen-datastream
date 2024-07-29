# Install Instructions for ngen-datastream
These steps are provided [scripted](#scripts) or [step-by-step](#step-by-step). Note some steps are specific to either `x86` or `aarch64`

## Prerequisites
* Linux OS
* Docker
* git

These instructions assume launching an instance from a blank Amazon 2023 Linux image. Steps may vary depending on your specific linux distribution.

## Scripted
1) Clone this repository
```
git clone https://github.com/CIROH-UA/ngen-datastream.git
```
2) Execute the startup script
```
cd ngen-datastream && ./scripts/install.sh
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
`aws_configure` if you intend to mount an s3 bucket or reference a bucket in the configuration.

You're ready to run ngen-datastream!

