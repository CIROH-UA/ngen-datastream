terraform {
  backend "s3" {}

  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  description = "AWS region where all resources will be deployed"
}

# Lambda Functions - Orchestration Components
variable "starter_lambda_name" {
  description = "Name of the Lambda function that launches EC2 instances from AMI to run datastream workloads"
}

variable "commander_lambda_name" {
  description = "Name of the Lambda function that sends shell commands to EC2 instances via SSM to execute datastream scripts"
}

variable "poller_lambda_name" {
  description = "Name of the Lambda function that polls EC2 instance status and monitors command execution progress"
}

variable "checker_lambda_name" {
  description = "Name of the Lambda function that validates datastream output exists in S3 after execution completes"
}

variable "stopper_lambda_name" {
  description = "Name of the Lambda function that terminates EC2 instances after datastream execution"
}

# Lambda IAM Configuration
variable "lambda_policy_name" {
  description = "Name of the IAM policy granting Lambda functions permissions for EC2, SSM, and S3 operations"
}

variable "lambda_role_name" {
  description = "Name of the IAM role assumed by all orchestration Lambda functions"
}

variable "lambda_invoke_policy_name" {
  description = "Name of the IAM policy allowing Step Functions state machine to invoke Lambda functions"
}

# Step Functions State Machine Configuration
variable "sm_name" {
  description = "Name of the Step Functions state machine that orchestrates the datastream workflow (Starter -> Commander -> Poller -> Checker -> Stopper)"
}

variable "sm_role_name" {
  description = "Name of the IAM role assumed by the Step Functions state machine to invoke Lambda functions"
}

# EC2 Instance IAM Configuration
variable "ec2_role" {
  description = "Name of the IAM role assumed by EC2 instances running datastream workloads, enabling SSM connectivity and S3 access"
}

variable "ec2_policy_name" {
  description = "Name of the IAM policy attached to EC2 role granting SSM, S3, and EC2 describe permissions"
}

variable "profile_name" {
  description = "Name of the IAM instance profile that wraps the EC2 role, attached to EC2 instances at launch"
}

variable "resource_prefix" {
  type        = string
  description = "Prefix for resource naming (e.g., 'nrds_dev', 'nrds_prod')"
}

variable "scheduler_policy_name" {}
variable "scheduler_role_name" {}

# Schedules Configuration
variable "routing_only_ami_id" {
  description = "AMI ID for Routing-Only model EC2 instances"
  default     = "ami-0e6cb37ae70ddb282"
}

variable "environment_suffix" {
  type        = string
  description = "Environment suffix for schedule names (e.g., 'dev', 'prod', 'test')"
}

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
}

module "nrds_schedules" {
  source = "./modules/schedules"

  region                = var.region
  scheduler_policy_name = var.scheduler_policy_name
  scheduler_role_name   = var.scheduler_role_name

  # Orchestration outputs
  state_machine_arn    = module.nrds_orchestration.datastream_arn
  ec2_instance_profile = module.nrds_orchestration.ec2_instance_profile_name
  ec2_security_groups  = [module.nrds_orchestration.ec2_security_group_id]

  # Schedule configuration
  routing_only_ami_id = var.routing_only_ami_id
  environment_suffix  = var.environment_suffix
  schedule_timezone   = var.schedule_timezone
  schedule_group_name = var.schedule_group_name

  depends_on = [module.nrds_orchestration]
}