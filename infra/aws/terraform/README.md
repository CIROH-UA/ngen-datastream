# NextGen Research DataStream AWS IaC
The Terraform in this folder builds the NextGen Research Datastream (NRDS) Amazon Web Services cloud infrastructure. The infrastructure is organized as independent **services**, each consuming a shared **orchestration** module.

## Directory Structure
```
infra/aws/terraform/
  modules/
    orchestration/        # Shared module: Step Functions, Lambdas, IAM, EC2
  services/
    nrds-routing-only/    # Routing-Only model service
      envs/
        test.tfvars       # Variable values for the test environment
        test.backend.hcl  # S3 backend config for the test environment
      modules/
        schedules/        # EventBridge schedules for this service
      main.tf
      variables.tf
    nrds-cfe-nom/         # CFE-NOM model service
      envs/
        test.tfvars
        test.backend.hcl
      modules/
        schedules/
      main.tf
      variables.tf
```

## Orchestration
With the orchestration module built, users can issue AWS StepFunction executions (via the CLI) that execute an AWS State Machine responsible for managing individual NextGen simulations on an AWS EC2 instance. This infra effectively gives users the ability to execute NextGen simulations in AWS cloud.

If desired, the commands are editable in an execution file, allowing this infra to be all-purpose (non-NextGen). Users can use this infrastructure to run any sort of ec2 based job in AWS cloud. An example for doing so has been demonstrated in the forcingprocessor repository to help in CI/CD ([link](https://github.com/CIROH-UA/forcingprocessor/blob/main/.github/executions/fp_ds_test_execution_arm.json)).

Note that this orchestration does not cost anything to build. A user's account will only incur costs when the AWS State Machine is executed.

## Scheduling
The NRDS infrastructure contains AWS EventBridge Schedules that trigger executions daily.

A "datastream" is created and scheduled by adding a schedule file similar to the [NRDS CFE NOM schedule Terraform file](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/modules/schedules/nrds_cfe_nom_schedules.tf), the accompanying [execution file templates](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/modules/schedules/executions/templates/execution_datastream_VPU_template.json), and a [generation script](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/python/src/research_datastream/gen_vpu_execs.py) to create those execution files.

## Remote State (S3 Backend)
Each service stores its Terraform state in the `ciroh-terraform-state` S3 bucket with native S3 state locking (Terraform >= 1.10, no DynamoDB required). Backend configuration is split into partial `.hcl` files per environment:

| Service | State Key | Backend Config |
|---------|-----------|----------------|
| nrds-routing-only | `routing-only-test-datastream/terraform.tfstate` | `envs/test.backend.hcl` |
| nrds-cfe-nom | `cfe-nom-test-datastream/terraform.tfstate` | `envs/test.backend.hcl` |

# AWS
In order to go from cloning this repository to executing NextGen simulations in AWS cloud, see this [document](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/docs/GETTING_STARTED.md).
See [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/docs/ARCHITECTURE.md) for a technical explanation of the Amazon Web Services (AWS) infrastructure architecture. See [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/docs/AWS_BASICS.md) for a crash course in AWS basics relevant to this tooling. See [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/docs/TERRAFORM_BASICS.md) for a crash course in Terraform basics relevant to this tooling.

# Prerequisites
* AWS account with credentials configured
* Terraform >= 1.10
* Linux / macOS

## Build AWS Infrastructure
Construct AWS State Machine, Lambdas, Policies, and Roles. See [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/docs/ARCHITECTURE.md) for a more in-depth explanation of the infrastructure.

1) Open a terminal, log into AWS account
2) Navigate to the service you want to deploy:
```bash
cd infra/aws/terraform/services/nrds-routing-only
# or
cd infra/aws/terraform/services/nrds-cfe-nom
```
3) Initialize Terraform with the backend config for your environment:
```bash
terraform init -backend-config=envs/test.backend.hcl
```
4) Review the plan:
```bash
terraform plan -var-file=envs/test.tfvars
```
5) Apply:
```bash
terraform apply -var-file=envs/test.tfvars
```

## Execute AWS State Machine
This command will execute the AWS State Machine, which will start and manage an EC2 instance to run the datastream command. See [GETTING_STARTED.md](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/docs/GETTING_STARTED.md#create-execution-file) for more guidance on configuring the `execution.json`.
```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:###:stateMachine:<sm_name> \
  --name <your-execution-name> \
  --input "file://<path-to-execution-json>" \
  --region us-east-1
```

## Tear Down AWS Infrastructure
```bash
cd infra/aws/terraform/services/<service-name>
terraform init -backend-config=envs/test.backend.hcl
terraform destroy -var-file=envs/test.tfvars
```

## Partial Success (`terraform apply failure`)
`terraform apply` will fail if some of the resources already exist with the names defined in `envs/test.tfvars`. These resources must be either manually destroyed or imported. A script exists [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/shell/import_resources.sh) to automate importing any existing resources. Remove all spaces from variable file if using this script.
```bash
import_resources.sh <path-to-envs/test.tfvars>
```

## CI/CD Workflows
GitHub Actions workflows automate validation, deployment, and monitoring:

| Workflow | Trigger | Description |
|----------|---------|-------------|
| `terraform-pr-validate.yml` | PR to `main` | Format check, validate, plan, security scan |
| `terraform-deploy.yml` | Push to `main` | Sequential `terraform apply` per changed service |
| `terraform-drift-detection.yml` | Daily (6 AM UTC) | Detects infrastructure drift, creates GitHub Issues |
| `terraform-health-check.yml` | Post-deploy + every 6h | Verifies Step Functions state machines are ACTIVE |

Services are managed via a **SERVICE_REGISTRY** pattern in each workflow. To add a new service, add a path filter and a JSON entry to the registry -- no new jobs needed.
