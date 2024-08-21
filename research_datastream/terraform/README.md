The Terraform in this folder will stand up Amazon Web Services cloud infrastructure that allows users to run hydrologic numeric simulations remotely and within the NextGen Framework. These executions are performed with `ngen-datastream` tooling, which provides scalability, reproducibility, and ease of use. The cloud based components of the research datastream were constructed using this infrastructure. Implmentation of additional cloud providers is in development.

# AWS
In order to go from cloning this repository to executing NextGen simulations in AWS cloud, see this [document](https://github.com/CIROH-UA/ngen-datastream/tree/main/terraform/GETTING_STARTED.md).
See [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/terraform/ARCHITECTURE.md) for a technical explanation of the Amazon Web Services (AWS) infrastructure architecture. See [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/terraform/AWS_BASICS.md) for a crash course in AWS basics relevant to this tooling.

# Prerequisites
* AWS account
* Terraform
* Linux

## Building AWS State Machine
1) Open a terminal, log into AWS account
2) Customize resource names by editing `variables.tfvars`.
3) Build the state machine with Terraform
```
cd terraform
terraform init
terraform apply -var-file=./variables.tfvars
```

## Execute
```
aws stepfunctions start-execution \
--state-machine-arn arn:aws:states:us-east-1:###:stateMachine:<sm_name> \
--name <your-execution-name> \
--input "file://<path-to-execution-json>" \
--region us-east-1
```
