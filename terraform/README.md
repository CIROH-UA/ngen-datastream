# Prerequisites
* AWS account
* Terraform
* Linux

## Building AWS State Machine
1) Open a terminal, log into AWS account
2) Customize resource names by editing `variables.tfvars` 
3) Build the state machine with Terraform
```
cd terraform
terraform init
terraform apply -var-file=./variables.tfvars
```
### If you want to SSH into the launched instances:
1) Locate the security group that you want to control traffic to the ec2 instances. If you want the ability to SSH into the instances that the state machine lauches, make sure the security group allows for your inbound traffic.
2) Generate a key that you will use to authenticate your SSH session. Provide the name of that key in the execution json: 
```
"KeyName"            : "your_key_name",
```

## Execute a NextGen job
3) Create an execution json
```
cp ./executions/execution_template.json  ./executions/execution_test_1.json
```
3a) Open this file up and let's fill in everything you'll need
```
vi ./executions/execution_test_1.json
```
3b) Define the AMI ID. Read [here](#build-an-aws-machine-image-ami) for instructions on how to build your own. 
```
  "instance_parameters" :
  {
    "ImageId"            : "ami-###",
```
3c) Define the desired instance type. Make sure the hardware architecture matches the AMI.
```
    "InstanceType"       : "t2g.xlarge",
```
3d) Define the key that authenticates the user when SSH'ing into the instance. 
```
    "KeyName"            : "your_key.pem",
```
3e) Define the security group. Make sure it allows for inbound traffic if you want to SSH.
```
    "SecurityGroupIds"   : ["sg-###"],
```
3f) This must match `profile_name` in variables.tfvars
```
    "IamInstanceProfile" : {
        "Name" : "name-of-instance-profile"
        },
```
3g) Name for the instance
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
3h) Define the disk size for the instance
```
    "BlockDeviceMappings":[
      {
          "DeviceName": "/dev/xvda",  
          "Ebs": {
              "VolumeSize": 64,
              "VolumeType": "gp2"  
          }
      }
    ]
```
3i) Define the region. Make sure this matches the region the state machine exists in.
```
  "region"   : "us-east-1",
```
3j) Provide the commands you want the instance to execute. Below is an example to create a directory, mount a bucket to the instance, and run a `ngen-datastream` execution that will copy the data directory to the bucket before terminating.
```
  "commands"  : [
    "runuser -l ec2-user -c 'mkdir -p /home/ec2-user/ngen-datastream/data/mount'",
    "runuser -l ec2-user -c 'mount-s3 ngen-datastream /home/ec2-user/ngen-datastream/data/mount'",
    "runuser -l ec2-user -c 'cd /home/ec2-user/ngen-datastream && ./scripts/stream.sh -s 202406100100 -e 202406100200 -g https://lynker-spatial.s3.amazonaws.com/hydrofabric/v20.1/gpkg/nextgen_09.gpkg -R ./configs/ngen/realization_sloth_nom_cfe_pet.json -S ./data/mount -o /test -n 4'"
  ],
```
3k) The state machine will confirm a complete execution by checking for the existence of an s3 object. Set the bucket and object key to look for here. `ngen-datastream` will always create a `ngen-run.tar.gz` file that can be found at `s3://<bucket>/<prefix>/ngen-run.tar.gz`
```
  "bucket"   : "",
  "obj_key"  : ""
```

## Build an AWS Machine Image (AMI)
1) Launch any instance with a Linux OS.
2) SSH into the instance and install `ngen-datastream`. See [install instructions](https://github.com/CIROH-UA/ngen-datastream/blob/main/INSTALL.md).
3) Stop instance and create an image from it.
