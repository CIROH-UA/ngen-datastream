provider "aws" {
  region = var.region
}

terraform {
  required_version = ">= 0.12"
}

variable "region" {}
variable "scheduler_policy_name" {}
variable "scheduler_role_name" {}

variable "state_machine_arn" {
  type = string
}

locals {
    vpus = [
    "fp","01","02","03N","03S","03W","04",
    "05","06","07","08","09","10L",
    "10U","11","12","13","14","15",
    "16","17","18"
  ]
}
