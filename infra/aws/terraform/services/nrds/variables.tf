variable "region" {
  type        = string
  description = "AWS region"
}

# Orchestration
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
variable "resource_prefix" {
  type        = string
  description = "Prefix for resource naming"
}

# Shared scheduler IAM
variable "scheduler_policy_name" {
  type        = string
  description = "Name of the shared scheduler IAM policy"
}

variable "scheduler_role_name" {
  type        = string
  description = "Name of the shared scheduler IAM role"
}

# Per-datastream AMIs
variable "routing_only_ami_id" {
  type        = string
  description = "AMI ID for Routing-Only model EC2 instances"
  default     = "ami-0f8e27ecfe91ffd4f"
}

# Schedule settings
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
  description = "Environment suffix for schedule names (e.g., 'dev', 'prod')"
}

# S3
variable "s3_bucket" {
  type        = string
  description = "S3 bucket name for datastream resources and outputs"
  default     = "ciroh-community-ngen-datastream"
}
