This document serves as a crash course on the Amazon Web Services (AWS) concepts a user will likely encounter while using `ngen-datastream` tooling. 

# Pricing
This section is first diliberately. AWS is a pay-for-time service which are fantastic for exploratory processing, but can be expensive for long running tasks or poorly designed aritectures. See [here](https://aws.amazon.com/blogs/architecture/overview-of-data-transfer-costs-for-common-architectures/) to better understand the potential costs of insteracting with AWS. `ngen-datastream` tooling was designed with cost savings in mind. For example, the spawned instances are polled and shut down immediately upon completion of the requested jobs, avoiding incurring run-time costs needlessly.

# Amazon Step Function State Machines
An [AWS State Machine](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-statemachines.html) is an implmentation of the Step Functions service. It is essentially a collection of AWS Lambda Functions, which interact through logical specifications and data sharing. 

# Amazon Lambda Functions
An [AWS Lambda Function](https://aws.amazon.com/lambda/) is a small bit of code run in a serverless fashion. The lambda functions in this repository are written in python.

# Amazon Machine Images (AMIs)
This a template for an ec2 instance. An AMI is used to capture the exact development environment, effectively preserving the host artitecture, operating system, installed packages, and stored data such that an environment can be replicated exactly on a fresh host.

# Key pairs
When a user wants to access a remote host, a key is required to authenticate the user. This key is often supplied at the command line along with the ssh command. It will be required for the user to have generated an AWS key pair and have the key stored locally.
