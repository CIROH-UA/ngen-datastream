This document serves as a crash course on the Amazon Web Services (AWS) concepts a user will likely encounter while using `ngen-datastream` tooling. 

First, a quick summary of what the terraform in this repository does. A technical explanation exists [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/terraform/ARCHITECTURE.md).

# Amazon Machine Images (AMIs)
This a template for an ec2 instance. An AMI is used to capture the exact development environment, effectively preserving the host artitecture, operating system, installed packages, and stored data such that an environment can be replicated exactly on a fresh host.