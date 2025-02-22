This document will step users through the following
1) Building the AWS infrastructure with Terraform
2) Preparing a custom Amazon Machine Image with the AWS Console
3) Configuring an execution file
4) Executing the the State Machine

## 1. Build the infrastructure
You can find that back in the [terraform README](https://github.com/CIROH-UA/ngen-datastream/tree/main/research_datastream/terraform#build-aws-infrastructure)

## 2. Build an Amazon Machine Image
Before we can issue an execution, we must first have an [AMI](https://github.com/CIROH-UA/ngen-datastream/blob/main/research_datastream/terraform/AWS_BASICS.md#6-amazon-machine-images-amis) to spawn an instance from. To create an AMI, we will launch an instance from the template AWS Linux 2023 AMI and install ngen-datastream. The following steps are shown through the AWS Console.

### Launch instance
Pick a region to launch your instance in, here it is `us-east-2`. Also pick a name, here `terraform_demo`. Select the Amazon Linux 2023 AMI as seen below.

![launch_1](./images/launch_instance_1.jpg)

Next, define the architecture. Here, we request an ARM based host. Note that the AMI will be architecture specific, so you can only spawn ARM typed ec2 instances from an ARM AMI. Here we select a `t4g.large` ARM instance with 2 vCPUs and 8 GiB of memory. Select the key you wish to use to ssh into the instance; create a new key if needed.

![launch_2](./images/launch_instance_2.jpg)

Lastly, define a security group to which the instance will belong. Typically a user has default security groups available, which should be fine to use. Also configure the volume size, here we will mount a 32 GiB drive. Launch the instance.

![launch_3](./images/launch_instance_3.jpg)

SSH into the instance by providing the path to the key pair file. Find the instance in the AWS console to retrieve the Public IPv4 DNS address. The following steps occur in a local linux terminal. 
```
ssh -i <path_to_your_key> ec2-user@<Public_IPv4_DNS_address>
```

### Install ngen-datastream
First, install docker
```
sudo dnf install docker -y && sudo systemctl start docker && sudo usermod -aG docker ec2-user && sudo newgrp docker
```
This will set your user to `root`. Type `exit` to return back to `ec2-user`. Then type `exit` again to exit the ssh session. ssh back into the instance and check that the docker daemon in running properly with `docker run hello-world`.

Second, install required packages
```
curl -L -O https://github.com/lynker-spatial/hfsubsetCLI/releases/download/v1.1.0/hfsubset-v1.1.0-linux_arm64.tar.gz && tar -xzvf hfsubset-v1.1.0-linux_arm64.tar.gz && sudo mv ./hfsubset /usr/bin/hfsubset && sudo dnf install git pip pigz awscli -y
```

Next, clone this repository
```
git clone https://github.com/CIROH-UA/ngen-datastream.git
```

At this point, the instance is in an appropriate state for `ngen-datastream` executions. If you would like to store the `ngen-datastream` docker images with the AMI as well, you can pull them with these commands
```
docker pull awiciroh/datastream:latest
docker pull awiciroh/forcingprocessor:latest
docker pull awiciroh/ciroh-ngen-image:latest
docker pull zwills/merkdir
```
This is not requried, but will save on execution time at the expensive of AMI size.

### Create AMI from instance
Head back to the AWS console and find your instance and create an image from it. Note that this will shut down the instance and you will not be able to SSH into it during the image creation. The SSH session will end in your local linux terminal.

![ami](./images/create_AMI.jpg)

Hold on to the AMI ID.

![ami](./images/create_AMI2.jpg)

## 3. Configure Execution File
Create an execution json. The user has 2 templates to begin from. These templates are identical, with the exception that execution_template_datastream.json has the field "datastream_command_options", whereas execution_template_general_purpose.json has the field "commands". The reason for this is to make the executions as readable as possible, while still preserving the general purpose nature of this architecture. The following commands are performed in a local linux terminal with the working directory being `/ngen-datastream/research_datastream/terraform`. 

```
cp ./executions/execution_template_<pick_one>.json  ./executions/execution_test_1.json
```

Open file to configure the execution
```
vi ./executions/execution_test_1.json
```

Provide the commands you want the instance to execute. 
Starting from execution_template_datastream. These options correspond directly to the cli args for `ngen-datastream/scripts/ngen-datastream`
```
  "datastream_command_options" : {
    "start_time"          : "202006200100",
    "end_time"            : "202006210000",
    "forcing_source"      : "NWM_RETRO_V3",
    "realization"         : "$(pwd)/configs/ngen/realization_sloth_nom_cfe_pet.json",
    "nprocs"              : "4",
    "subset_id_type"      : "hl",
    "subset_id"           : "Gages-09106150",
    "hydrofabric_version" : "2.1.1",
    "s3_bucket"           : "ngen_datstream",
    "s3_prefix"       : "datastream_cloud_test"
  }
```

Starting from execution_template_general_purpose. Make sure to wrap commands in `runuser -l ec2-user -c`.
```
  "commands"  : [
    "runuser -l ec2-user -c '<first_command>'",
    "runuser -l ec2-user -c '<subsequent_commands...>'"
],
```

Edit Run Options
```
  "run_options":{
    "ii_terminate_instance" : true,
    "ii_delete_volume"      : false,
    "ii_check_s3"           : true,
    "timeout_s"             : 3600
},
```
If `s3_bucket` and `s3_prefix` are provided in `datastream_command_options` and `ii_check_s3` is set to `true` , the state machine will confirm that at least one object exists at `s3://<s3_bucket>/<s3_prefix>/`. 

`ii_terminate_instance` and `ii_delete_volume` allow the user to clean up AWS resources to avoid needless costs. While stopped instances do not incur costs, detached volumes do incur costs until deleted. 

`timeout_s` is a timeout for the commands issued during execution. This is valuable for shutting down hanging instances that may become unresponsive due to memory overflow, etc. Default is 3600.

Edit Instance Options
4) Define the AMI ID. 
```
  "instance_parameters" :
  {
    "ImageId"            : "ami-###",
```
Define the desired instance type. Make sure the hardware architecture matches the AMI.
```
    "InstanceType"       : "t2g.xlarge",
```
Define the key that authenticates the user when SSH'ing into the instance. Don't include the file extension (i.e. `.pem`).  
```
    "KeyName"            : "your_key",
```
This must match `profile_name` in variables.tfvars
```
    "IamInstanceProfile" : {
        "Name" : "name-of-instance-profile"
        },
```
Name for the instance
```
    "TagSpecifications"   :[
      {
          "ResourceType": "instance",
          "Tags": [
              {
                  "Key"   : "Name",
                  "Value" : "whatever-name-you-want"
              }
          ]
      }
```
Define the disk size and type for the instance
```
    "BlockDeviceMappings":[
      {
          "DeviceName": "/dev/xvda",  
          "Ebs": {
              "VolumeSize": 64,
              "VolumeType": "gp3"  
          }
      }
    ]
```

## 4. Execute the state machine. 
Issue this command from a local linux terminal from the `terraform` folder.
```
aws stepfunctions start-execution \
--state-machine-arn <sm_ARN> \
--name your-execution-name \
--input "file://$(pwd)/executions/execution_test_1.json" \
--region us-east-2
```

`state-machine-arn` can be found in the text file "sm_ARN.txt", which is generated during `terraform apply`.
