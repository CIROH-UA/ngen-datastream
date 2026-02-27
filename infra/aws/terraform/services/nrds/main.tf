provider "aws" {
  region = var.region
}

terraform {
  required_version = ">= 1.10"

  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

# =============================================================================
# Shared Orchestration (one state machine, one set of lambdas, one IAM setup)
# =============================================================================
module "nrds_orchestration" {
  source = "../../modules/orchestration"

  region                    = var.region
  starter_lambda_name       = var.starter_lambda_name
  commander_lambda_name     = var.commander_lambda_name
  poller_lambda_name        = var.poller_lambda_name
  checker_lambda_name       = var.checker_lambda_name
  stopper_lambda_name       = var.stopper_lambda_name
  lambda_policy_name        = var.lambda_policy_name
  lambda_role_name          = var.lambda_role_name
  lambda_invoke_policy_name = var.lambda_invoke_policy_name
  sm_name                   = var.sm_name
  sm_role_name              = var.sm_role_name
  ec2_role                  = var.ec2_role
  ec2_policy_name           = var.ec2_policy_name
  profile_name              = var.profile_name
  resource_prefix           = var.resource_prefix
}

# =============================================================================
# Datastream Schedules
# To add a new datastream: add a module block here and a directory under datastreams/
# =============================================================================

module "cfe_nom_schedules" {
  source = "./datastreams/cfe-nom"

  region               = var.region
  state_machine_arn    = module.nrds_orchestration.datastream_arn
  scheduler_role_arn   = aws_iam_role.scheduler_role.arn
  ec2_instance_profile = module.nrds_orchestration.ec2_instance_profile_name

  cfe_nom_ami_id = var.cfe_nom_ami_id
  fp_ami_id      = var.fp_ami_id

  schedule_timezone   = var.schedule_timezone
  schedule_group_name = var.schedule_group_name
  environment_suffix  = var.environment_suffix

  s3_bucket = var.s3_bucket
}
