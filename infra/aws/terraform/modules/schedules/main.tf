provider "aws" {
  region = var.region
}

terraform {
  required_version = ">= 0.12"
}

variable "region" {}
variable "scheduler_policy_name" {}
variable "scheduler_role_name" {}
