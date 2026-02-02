provider "aws" {
  region = var.region
}

variable "region" {}
variable "starter_lambda_name" {}
variable "commander_lambda_name" {}
variable "poller_lambda_name" {}
variable "checker_lambda_name" {}
variable "stopper_lambda_name" {}
variable "lambda_policy_name" {}
variable "lambda_role_name" {}
variable "lambda_invoke_policy_name" {}
variable "sm_name" {}
variable "sm_role_name" {}
variable "ec2_role" {}
variable "ec2_policy_name" {}
variable "profile_name" {}

variable "scheduler_policy_name" {}
variable "scheduler_role_name" {}

# VPC Configuration - fetch default VPC automatically
data "aws_vpc" "default" {
  default = true
}

variable "resource_prefix" {
  type        = string
  description = "Prefix for resource naming (e.g., 'nrds_test', 'nrds_prod')"
}

# EC2 Configuration
variable "ec2_instance_profile" {
  type        = string
  description = "IAM instance profile name for EC2"
}

# Model-specific AMIs
variable "cfe_nom_ami_id" {
  type        = string
  description = "AMI ID for CFE_NOM model EC2 instances"
  default     = "ami-0ef008a1e6d9aa12d"
}

# Schedule Settings
variable "schedule_timezone" {
  type        = string
  description = "Timezone for EventBridge schedules"
  default     = "America/New_York"
}

variable "schedule_group_name" {
  type        = string
  description = "EventBridge scheduler group name"
  default     = "default"
}

variable "environment_suffix" {
  type        = string
  description = "Environment suffix for schedule names (e.g., 'dev', 'prod', 'test')"
}

module "nrds_orchestration" {
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
  vpc_id                    = data.aws_vpc.default.id
}

module "nrds_schedules" {
  source = "./modules/schedules"

  region                = var.region
  scheduler_policy_name = var.scheduler_policy_name
  scheduler_role_name   = var.scheduler_role_name
  state_machine_arn     = module.nrds_orchestration.datastream_arn

  # EC2 config
  ec2_security_groups  = [module.nrds_orchestration.ec2_security_group_id]
  ec2_instance_profile = var.ec2_instance_profile

  # Model AMI
  cfe_nom_ami_id = var.cfe_nom_ami_id

  # Schedule settings
  schedule_timezone   = var.schedule_timezone
  schedule_group_name = var.schedule_group_name
  environment_suffix  = var.environment_suffix
}