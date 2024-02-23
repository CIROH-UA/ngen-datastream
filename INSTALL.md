# Install Instructions for ngen-datastream
ngen-datastream is designed for linux operating systems. These instructions assuming starting from a freshly launched host.

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