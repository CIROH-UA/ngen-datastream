The Terraform in this folder will stand up Amazon Web Services cloud infrastructure that allows users to run hydrologic numeric simulations remotely and within the NextGen Framework. These executions are performed with `ngen-datastream` tooling, which provides scalability, reproducibility, and ease of use. The cloud based components of the research datastream were constructed using this infrastructure.

# AWS
In order to go from cloning this repository to executing NextGen simulations in AWS cloud, see this [document](https://github.com/CIROH-UA/ngen-datastream/blob/main/research_datastream/terraform/GETTING_STARTED.md).
See [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/research_datastream/terraform/ARCHITECTURE.md) for a technical explanation of the Amazon Web Services (AWS) infrastructure architecture. See [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/research_datastream/terraform/AWS_BASICS.md) for a crash course in AWS basics relevant to this tooling.

# Prerequisites
* AWS account
* Terraform
* Linux

## Build AWS Infrastructure
Construct AWS State Machine, Lambdas, Policies, and Roles. See [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/research_datastream/terraform/ARCHITECTURE.md) for a more indepth explanation of the infrastrucutre.
1) Open a terminal, log into AWS account
2) Customize resource names by editing `variables.tfvars`. Names must be unqiue and not correspond to already existing resources. 
3) Build the state machine with Terraform
```
cd terraform
terraform init
terraform apply -var-file=./variables.tfvars
```

## Execute AWS State Machine
This command will execute the aws state machine, which will start and manage an ec2 instance to run the datastream command. See [GETTING_STARTED.md](https://github.com/CIROH-UA/ngen-datastream/blob/main/research_datastream/terraform/GETTING_STARTED.md#create-execution-file) for more guidance on configuring the `execution.json`.
```
aws stepfunctions start-execution \
--state-machine-arn arn:aws:states:us-east-1:###:stateMachine:<sm_name> \
--name <your-execution-name> \
--input "file://<path-to-execution-json>" \
--region us-east-1
```

## Tear Down AWS Infrastructure
```
terraform destroy -var-file=./variables.tfvars
```

## Partial Success (`terraform apply failure`)
`terraform apply` will fail if some of the resources already exist with the names defined in `variables.tfvars`. These resources must be either manually destroyed or imported. A script exists [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/research_datastream/research_datastream/scripts/import_resources.sh) to automate importing any existing resources. Remove all spaces from variable file if using this script.
```
import_resources.sh <path-to-variables.tfvars>
```
