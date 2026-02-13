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
    "fp", "01", "02", "03N", "03S", "03W", "04",
    "05", "06", "07", "08", "09", "10L",
    "10U", "11", "12", "13", "14", "15",
    "16", "17", "18"
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
