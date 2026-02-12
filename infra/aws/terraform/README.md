# NextGen Research DataStream AWS IaC
The Terraform in this folder will build the NextGen Research Datastream (NRDS) Amazon Web Services cloud infrastructure. This terraform is separated into two modules, orchestration and scheduling.

## Orchestration
With the orchestration module built, users can issue AWS StepFunction executions (via the CLI) that execute an AWS State Machine responsible for managing individual NextGen simulations on an AWS EC2 instance. This infra effectively gives users the ability to execute NextGen simulations in AWS cloud.

If desired, the commands are editable in an execution file, allowing this infra to be all-purpose (non-NextGen). Users can use this infrastructure to run any sort of ec2 based job in AWS cloud. An example for doing so has been demonstrated in the forcingprocessor repository to help in CI/CD ([link](https://github.com/CIROH-UA/forcingprocessor/blob/main/.github/executions/fp_ds_test_execution_arm.json)).

Note that this orchestration does not cost anything to build. A user's account will only incur costs when the AWS State Machine is executed.

## Scheduling
The scheduling module uses `templatefile()` to dynamically generate AWS EventBridge Schedules from a config JSON and a `.tpl` template. No hardcoded execution files needed.

- **Config**: `modules/schedules/config/execution_forecast_inputs_routing_only.json` defines init cycles, VPU-to-instance-type mappings, and volume size
- **Template**: `modules/schedules/executions/templates/execution_datastream_routing_only_VPU_template.json.tpl` defines the execution payload (commands, run options, instance parameters)
- **Schedules**: `modules/schedules/routing_only_schedules.tf` uses `for_each` over init_cycles x VPUs to create schedules

Currently configured for **Routing-Only** (VPU 03W, short_range, 24 init cycles).

# Prerequisites
* AWS account
* Terraform >= 1.0
* AWS CLI configured

## Build AWS Infrastructure
Construct AWS State Machine, Lambdas, Policies, Roles, and Schedules.

1) Open a terminal, log into AWS account
2) Customize resource names by editing `variables.tfvars`. Names must be unique and not correspond to already existing resources.
3) Build the infrastructure with Terraform
```bash
cd infra/aws/terraform
terraform init -backend-config=backend-routing-only.hcl
terraform apply -var-file=variables.tfvars
```

## Execute AWS State Machine
This command will execute the aws state machine, which will start and manage an ec2 instance to run the datastream command.
```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:###:stateMachine:<sm_name> \
  --name <your-execution-name> \
  --input "file://<path-to-execution-json>" \
  --region us-east-1
```

## Tear Down AWS Infrastructure
```bash
terraform destroy -var-file=variables.tfvars
```

## State Configuration

| Environment | Backend Config | Variables | State Path |
|-------------|----------------|-----------|------------|
| routing-only | `backend-routing-only.hcl` | `variables.tfvars` | `s3://ciroh-terraform-state/ngen-routing_only-datastream/terraform.tfstate` |

### Using the Environment
```bash
# Initialize with backend
terraform init -backend-config=backend-routing-only.hcl

# Apply
terraform apply -var-file=variables.tfvars

# Destroy
terraform destroy -var-file=variables.tfvars
```

## Partial Success (`terraform apply failure`)
`terraform apply` will fail if some of the resources already exist with the names defined in `variables.tfvars`. These resources must be either manually destroyed or imported. A script exists [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/shell/import_resources.sh) to automate importing any existing resources. Remove all spaces from variable file if using this script.
```bash
import_resources.sh <path-to-variables.tfvars>
```
