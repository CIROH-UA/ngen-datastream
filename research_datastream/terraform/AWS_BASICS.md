This document serves as a crash course on the Amazon Web Services (AWS) concepts a user will likely encounter while using `ngen-datastream` tooling. 

# Pricing
This section is first diliberately. AWS is a pay-for-time service which is fantastic for exploratory processing, but can be expensive for long running tasks or poorly designed aritectures. See [here](https://aws.amazon.com/blogs/architecture/overview-of-data-transfer-costs-for-common-architectures/) to better understand the potential costs of insteracting with AWS. `ngen-datastream` tooling was designed with cost savings in mind. For example, the spawned [ec2 instances](#ec2-instance) are polled and shut down immediately upon completion of the requested jobs, avoiding needlessly incurring run-time costs. Also, the option exists to dismount the storage volume upon execution completion, `ii_delete_volume`. Note that this will render the instance inaccessible and the data local to that storage volume will no longer be accessible.

# Step Function State Machines
An [AWS State Machine](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-statemachines.html) is an implmentation of the Step Functions service. It is essentially a collection of AWS Lambda Functions, which interact through logical specifications and data sharing. 

# Lambda Functions
An [AWS Lambda Function](https://aws.amazon.com/lambda/) is a small bit of code run in a serverless fashion. The lambda functions in this repository are written in python.

# EC2 Instance
A virtual computer that exists in the "cloud". AWS allows users to choose the number of vCPUs, memory size, storage size, hardward architecture, and operating system. Amazon offers base [AMIs](#machine-images-amis) from which to lanuch instances, but users can also make custom [AMIs](#machine-images-amis).

# Machine Images (AMIs)
This a template for an [ec2 instance](#ec2-instance). An AMI is used to capture the exact development environment, effectively preserving the host artitecture, operating system, installed packages, and stored data such that an environment can be replicated exactly on a fresh instance.

# Key pairs
When a user wants to access a remote host ([ec2 instance](#ec2-instance)), a key is required to authenticate the user. This key is often supplied at the command line along with the ssh command. It will be required for the user to have generated an AWS key pair and have the key stored locally.