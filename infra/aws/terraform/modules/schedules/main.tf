provider "aws" {
  region = var.region
}

terraform {
  required_version = ">= 0.12"
}

variable "region" {}
variable "scheduler_policy_name" {}
variable "scheduler_role_name" {}
variable "s3_bucket" {}
variable "ec2_profile_name" {}
variable "security_group_id" {}
variable "key_name" {}
variable "ami_id_fp" {}
variable "ami_id_vpu" {}
variable "state_machine_arn" {}
