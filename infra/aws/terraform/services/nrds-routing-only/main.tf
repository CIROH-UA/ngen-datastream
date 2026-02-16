provider "aws" {
  region = var.region
}

terraform {
  required_version = ">= 1.10"

  backend "s3" {
    bucket       = "ciroh-terraform-state"
    key          = "routing-only-test-datastream/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }

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

module "schedules" {
  source = "./modules/schedules"

  region                = var.region
  scheduler_policy_name = var.scheduler_policy_name
  scheduler_role_name   = var.scheduler_role_name
  state_machine_arn     = module.nrds_orchestration.datastream_arn

  # EC2 config from orchestration
  ec2_security_groups  = [module.nrds_orchestration.ec2_security_group_id]
  ec2_instance_profile = module.nrds_orchestration.ec2_instance_profile_name

  # Model AMI
  routing_only_ami_id = var.routing_only_ami_id

  # Schedule settings
  schedule_timezone   = var.schedule_timezone
  schedule_group_name = var.schedule_group_name
  environment_suffix  = var.environment_suffix
}
