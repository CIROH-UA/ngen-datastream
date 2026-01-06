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
  description = "Name of the Step Functions state machine that orchestrates the datastream workflow (Starter → Commander → Poller → Checker → Stopper)"
}

variable "sm_role_name" {
  description = "Name of the IAM role assumed by the Step Functions state machine to invoke Lambda functions"
}

variable "sm_parameter_name" {
  description = "SSM Parameter Store path where the state machine ARN is stored for reference by other services"
  default     = "/datastream/state-machine-arn"
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

# variable "scheduler_policy_name" {}
# variable "scheduler_role_name" {}

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
  sm_parameter_name         = var.sm_parameter_name
  ec2_role                  = var.ec2_role
  ec2_policy_name           = var.ec2_policy_name
  profile_name              = var.profile_name
}

# module "nrds_schedules" {
#   source = "./modules/schedules"
# 
#   region                = var.region
#   scheduler_policy_name = var.scheduler_policy_name
#   scheduler_role_name   = var.scheduler_role_name
# 
#   depends_on = [module.nrds_orchestration]
# }