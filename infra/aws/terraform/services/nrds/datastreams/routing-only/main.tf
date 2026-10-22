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
  vpu_resource_overrides = {
    # "17" = {
    #   geopackage = "resources/v2.2_hydrofabric/geopackages/VPU_17/nextgen_VPU_17_v2.gpkg"
    # }
  }
  vpu_resources = {
    for vpu in var.all_vpus : vpu => merge({
      geopackage = "resources/v2.2_hydrofabric/geopackages/VPU_${vpu}/nextgen_VPU_${vpu}.gpkg"
    }, try(local.vpu_resource_overrides[vpu], {}))
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

variable "all_vpus" {
  type        = list(string)
  description = "All VPUs; this datastream deploys a subset of them"
}
