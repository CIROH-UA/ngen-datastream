# NRDS Infrastructure Deployment Guide

This guide explains how to configure and deploy NRDS (National Research Datastream) infrastructure using Terraform and GitHub Actions.

## Overview

The deployment workflow automatically:
1. Validates Terraform configuration
2. Deploys infrastructure (Lambdas, Step Functions, IAM roles)
3. Runs a test VPU execution
4. Cleans up resources (during PR testing)

## Configuration Files

### `variables.tfvars`

Contains all resource names for your environment. Update these values to create a new environment:

```hcl
region                    = "us-east-1"
sm_name                   = "nrds_dev_sm"              # State machine name
sm_role_name              = "nrds_dev_sm_role"
starter_lambda_name       = "nrds_dev_start_ec2"
commander_lambda_name     = "nrds_dev_ec2_commander"
poller_lambda_name        = "nrds_dev_ec2_poller"
checker_lambda_name       = "nrds_dev_s3_checker"
stopper_lambda_name       = "nrds_dev_ec2_stopper"
lambda_policy_name        = "nrds_dev_lambda_policy"
lambda_role_name          = "nrds_dev_lambda_role"
lambda_invoke_policy_name = "nrds_dev_lambda_invoke_policy"
ec2_role                  = "nrds_dev_ec2_role"
ec2_policy_name           = "nrds_dev_ec2_policy"
profile_name              = "nrds_dev_ec2_profile"
```

### `backend.hcl`

Configures remote state storage. Each environment needs a unique state key:

```hcl
bucket       = "ciroh-terraform-state"
key          = "ngen-datastream/terraform.tfstate"  # Unique per environment
region       = "us-east-2"
encrypt      = true
use_lockfile = true
```

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│  1. terraform-check                                             │
│     - Runs fmt, validate, plan                                  │
│     - Security scans (tfsec, checkov)                          │
│     - Uses: backend.hcl + variables.tfvars                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. terraform-apply                                             │
│     - Creates: Lambdas, Step Functions, IAM roles              │
│     - Stores state machine ARN in SSM parameter                │
│       Path: /datastream/state-machine-arn                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. test-short-range-vpus                                       │
│     - Reads ARN from SSM (automatically)                       │
│     - Starts Step Function execution                            │
│     - Verifies S3 outputs                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. terraform-destroy                                           │
│     - Cleans up resources (runs on success or failure)         │
└─────────────────────────────────────────────────────────────────┘
```

## Creating a New Environment

### Same Files, Different Content (Recommended)

Simply update the content of existing files - **no workflow changes needed**:

1. **Edit `variables.tfvars`** - Change resource names
2. **Edit `backend.hcl`** - Change state key to avoid conflicts

The workflow automatically:
- Uses `variables.tfvars` for Terraform variables
- Uses `backend.hcl` for state configuration
- Reads state machine ARN from SSM parameter dynamically

### SSM Parameter Bridge

The state machine ARN is stored in SSM at `/datastream/state-machine-arn`. This allows the workflow to automatically discover the correct ARN regardless of what name you configure.

```
variables.tfvars                    Terraform creates
   sm_name = "my_sm"        ──►     State Machine: my_sm
                                           │
                                           ▼
                                    SSM Parameter
                                    /datastream/state-machine-arn
                                    = arn:aws:states:...:my_sm
                                           │
                                           ▼
                                    Workflow reads ARN
                                    (no hardcoding needed)
```

## Required AWS Resources

Before running the workflow, ensure these exist:

| Resource | Description |
|----------|-------------|
| `AWS_ROLE_ARN` | GitHub OIDC role (stored as repository secret) |
| S3 bucket | For Terraform state (configured in `backend.hcl`) |
| Security Group | For EC2 instances (referenced in execution templates) |
| Key Pair | For EC2 SSH access (default: `actions_key`) |

## Workflow Inputs

When triggering the workflow manually, you can specify:

| Input | Description | Default |
|-------|-------------|---------|
| `vpu` | VPU to test (e.g., 01, 02, 03N) | `01` |
| `date` | Date for testing (YYYYMMDD) | `20250905` |

## Customizing SSM Parameter Path

If you need a different SSM parameter path:

1. Add to `variables.tfvars`:
   ```hcl
   sm_parameter_name = "/custom/path/state-machine-arn"
   ```

2. Update the workflow SSM calls to use the new path

## Troubleshooting

### State Machine ARN Not Found

If you see errors about SSM parameter not found:
- Verify Terraform apply completed successfully
- Check SSM parameter exists: `aws ssm get-parameter --name "/datastream/state-machine-arn" --with-decryption`

### Terraform State Conflicts

If multiple environments share the same state:
- Ensure each environment has a unique `key` in `backend.hcl`
- Example: `key = "ngen-datastream/prod/terraform.tfstate"`

### Permission Errors

Verify the GitHub OIDC role has permissions for:
- Terraform state S3 bucket
- SSM Parameter Store
- EC2, Lambda, Step Functions, IAM operations
