terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

locals {
  vpus = [
    "03W"
  ]
}

variable "region" {}
variable "scheduler_policy_name" {}
variable "scheduler_role_name" {}

variable "state_machine_arn" {
  type = string
}

# EC2 Configuration
variable "ec2_security_groups" {
  type        = list(string)
  description = "Security group IDs for EC2 instances"
}

variable "ec2_instance_profile" {
  type        = string
  description = "IAM instance profile name for EC2"
}

# Model-specific AMIs
variable "routing_only_ami_id" {
  type        = string
  description = "AMI ID for Routing-Only model EC2 instances"
  default     = "ami-0f8e27ecfe91ffd4f"
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

variable "s3_bucket" {
  type        = string
  description = "S3 bucket name for datastream resources and outputs"
  default     = "ciroh-community-ngen-datastream"
}
