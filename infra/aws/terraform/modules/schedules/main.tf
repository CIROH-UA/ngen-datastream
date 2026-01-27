provider "aws" {
  region = var.region
}

terraform {
  required_version = ">= 0.12"
}

locals {
  vpus = [
    "09"
  ]
}
variable "region" {}
variable "scheduler_policy_name" {}
variable "scheduler_role_name" {}

variable "state_machine_arn" {
  type = string
}

# EC2 Configuration
variable "ec2_key_name" {
  type        = string
  description = "EC2 key pair name for SSH access"
}

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

variable "lstm_ami_id" {
  type        = string
  description = "AMI ID for LSTM model EC2 instances"
  default     = "ami-0bba768785947ef54"
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
