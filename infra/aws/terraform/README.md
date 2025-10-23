# NextGen Research DataStream AWS IaC
The Terraform in this folder will build the NextGen Research Datastream (NRDS) Amazon Web Services cloud infrastructure. This terraform is separated into two modules, orchestration and scheduling. 

## Orchestration
With the orchestration module built, users can issue AWS StepFunction executions (via the CLI) that execute an AWS State Machine responsible for managing individual NextGen simulations on an AWS EC2 instance. This infra effectively gives users the ability to execute NextGen simulations in AWS cloud. 

If desired, the commands are editable in an execution file, allowing this infra to be all-purpose (non-NextGen). Users can use this infrastrcutre to run any sort of ec2 based job in AWS cloud. An example for doing so has been demonstrated in the forcingprocessor repository to help in CI/CD ([link](https://github.com/CIROH-UA/forcingprocessor/blob/main/.github/executions/fp_ds_test_execution_arm.json)).

Note that this orchestration does not cost anything to build. A user's account will only incur costs when the AWS State Machine is executed. 

## Scheduling
The NRDS infrastructure contains AWS EventBridge Schedules that trigger executions daily. 

A "datastream" is created and scheduled by adding a schedule file similar to the [NRDS CFE NOM schedule Terraform file](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/modules/schedules/nrds_cfe_nom_schedules.tf), the accompanying [execution file templates](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/modules/schedules/executions/templates/execution_datastream_VPU_template.json), and a [generation script](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/python/src/research_datastream/gen_vpu_execs.py) to create those exection files.

# AWS
In order to go from cloning this repository to executing NextGen simulations in AWS cloud, see this [document](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/docs/GETTING_STARTED.md).
See [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/docs/ARCHITECTURE.md) for a technical explanation of the Amazon Web Services (AWS) infrastructure architecture. See [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/docs/AWS_BASICS.md) for a crash course in AWS basics relevant to this tooling. See [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/docs/TERRAFORM_BASICS.md) for a crash course in Terraform basics relevant to this tooling.

# Prerequisites
* AWS account
* Terraform
* Linux

## Build AWS Infrastructure
Construct AWS State Machine, Lambdas, Policies, and Roles. See [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/docs/ARCHITECTURE.md) for a more indepth explanation of the infrastrucutre.
1) Open a terminal, log into AWS account
2) Customize resource names by editing `variables.tfvars`. Names must be unqiue and not correspond to already existing resources. 
3) Build the state machine with Terraform
```
cd terraform
terraform init
terraform apply -var-file=./variables.tfvars
```

## Execute AWS State Machine
This command will execute the aws state machine, which will start and manage an ec2 instance to run the datastream command. See [GETTING_STARTED.md](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/docs/GETTING_STARTED.md#create-execution-file) for more guidance on configuring the `execution.json`.
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
`terraform apply` will fail if some of the resources already exist with the names defined in `variables.tfvars`. These resources must be either manually destroyed or imported. A script exists [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/shell/import_resources.sh) to automate importing any existing resources. Remove all spaces from variable file if using this script.
```
import_resources.sh <path-to-variables.tfvars>
```
