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
  }
}

# Read shared orchestration outputs from its state file
data "terraform_remote_state" "orchestration" {
  backend = "s3"
  config = {
    bucket = var.state_bucket
    key    = var.orchestration_state_key
    region = var.region
  }
}

module "schedules" {
  source = "./modules/schedules"

  region                = var.region
  scheduler_policy_name = var.scheduler_policy_name
  scheduler_role_name   = var.scheduler_role_name
  state_machine_arn     = data.terraform_remote_state.orchestration.outputs.datastream_arn

  # EC2 config from shared orchestration
  ec2_security_groups  = [data.terraform_remote_state.orchestration.outputs.ec2_security_group_id]
  ec2_instance_profile = data.terraform_remote_state.orchestration.outputs.ec2_instance_profile_name

  # Model AMI
  routing_only_ami_id = var.routing_only_ami_id

  # Schedule settings
  schedule_timezone   = var.schedule_timezone
  schedule_group_name = var.schedule_group_name
  environment_suffix  = var.environment_suffix
}
