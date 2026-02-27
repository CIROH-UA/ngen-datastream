# NextGen Research DataStream (NRDS) — AWS Infrastructure

Terraform configuration for the NRDS AWS cloud infrastructure. A single root module manages all shared orchestration resources and per-datastream EventBridge schedules.

## Directory Structure

```
infra/aws/terraform/
  modules/orchestration/          # Shared orchestration (state machine, lambdas, IAM)
  services/nrds/                  # Root module
    main.tf                       # Provider, backend, orchestration + datastream modules
    variables.tf                  # Unified variables
    outputs.tf                    # Unified outputs
    iam_scheduler.tf              # Shared scheduler IAM role
    envs/
      prod.backend.hcl            # S3 backend config
      prod.tfvars                 # Production variable values
    datastreams/
      cfe-nom/                    # CFE NOM schedule module
        schedules.tf              # Short range, medium range, AnA schedules
        config/                   # Forecast input configuration
        templates/                # Execution JSON templates
      forcing/                    # Forcing generation schedule module
        schedules.tf              # Short range, medium range, AnA schedules
        config/                   # Forecast input configuration
        templates/                # Execution JSON templates
```

## Architecture

- **Orchestration** (instantiated once): AWS Step Functions state machine, 5 Lambda functions, IAM roles/policies. This is datastream-agnostic — it manages EC2 instance lifecycle for any execution.
- **Schedules** (per datastream): EventBridge Scheduler rules that trigger state machine executions on a cron. Each datastream module receives the shared `scheduler_role_arn` and `state_machine_arn`.
- **Single Terraform state**: All resources live in one S3 backend (`nrds-prod/terraform.tfstate`).

## Prerequisites

- AWS account with OIDC configured for GitHub Actions
- Terraform >= 1.10
- AWS CLI (for manual operations)

## Deploy

```bash
cd infra/aws/terraform/services/nrds
terraform init -backend-config=envs/prod.backend.hcl
terraform plan -var-file=envs/prod.tfvars
terraform apply -var-file=envs/prod.tfvars
```

## Execute State Machine (Manual)

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:###:stateMachine:nrds_prod_sm \
  --name <your-execution-name> \
  --input "file://<path-to-execution-json>" \
  --region us-east-1
```

## Adding a New Datastream

1. Create a new directory under `services/nrds/datastreams/<name>/`
2. Add `main.tf` (variables), `schedules.tf` (EventBridge schedules), `outputs.tf`
3. Add `config/` and `templates/` with forecast inputs and execution templates
4. Add a module block in `services/nrds/main.tf` passing `scheduler_role_arn`, `state_machine_arn`, etc.
5. Add the AMI variable to `services/nrds/variables.tf` and `envs/prod.tfvars`
6. Run `terraform plan` to verify — no workflow changes needed

## CI/CD Workflows

| Workflow | Trigger | Description |
|----------|---------|-------------|
| `terraform-deploy.yml` | Push to main | Plan + apply with manual approval |
| `terraform-pr-validate.yml` | Pull request | Format check, validate, plan with PR comment |
| `terraform-drift-detection.yml` | Daily at 6 AM UTC | Detect infrastructure drift |

## Documentation

- [Getting Started](docs/GETTING_STARTED.md)
- [Architecture](docs/ARCHITECTURE.md)
- [AWS Basics](docs/AWS_BASICS.md)
- [Terraform Basics](docs/TERRAFORM_BASICS.md)
