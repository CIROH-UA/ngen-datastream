terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "region" {}

variable "scheduler_role_arn" {
  type        = string
  description = "ARN of the shared scheduler IAM role"
}

variable "state_machine_arn" {
  type = string
}

variable "ec2_instance_profile" {
  type        = string
  description = "IAM instance profile name for EC2"
}

variable "routing_only_ami_id" {
  type        = string
  description = "AMI ID for Routing-Only model EC2 instances"
}

variable "schedule_timezone" {
  type    = string
  default = "America/New_York"
}

variable "schedule_group_name" {
  type    = string
  default = "default"
}

variable "environment_suffix" {
  type = string
}

variable "s3_bucket" {
  type    = string
  default = "ciroh-community-ngen-datastream"
}
