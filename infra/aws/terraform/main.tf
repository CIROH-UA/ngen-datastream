provider "aws" {
  region = var.region
}

terraform {
  backend "s3" {}

  required_version = ">= 1.0"
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

module "orchestration" {
  source = "./modules/orchestration"

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
