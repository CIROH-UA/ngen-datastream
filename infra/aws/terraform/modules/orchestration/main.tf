provider "aws" {
  region = var.region
}

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

variable "region" {}
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
variable "s3_bucket" {
  type        = string
  description = "S3 bucket name for IAM policy scoping"
}
variable "fallback_instance_families" {
  type        = string
  description = "Comma-separated instance families the starter lambda may substitute (same size) when the primary type has no capacity"
  default     = "m7g,r8g"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "aws_vpc" "default" {
  default = true
}
