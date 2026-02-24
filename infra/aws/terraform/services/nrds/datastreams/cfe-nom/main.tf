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

variable "cfe_nom_ami_id" {
  type        = string
  description = "AMI ID for CFE_NOM model EC2 instances"
}

variable "fp_ami_id" {
  type        = string
  description = "AMI ID for forcing processor EC2 instances"
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
