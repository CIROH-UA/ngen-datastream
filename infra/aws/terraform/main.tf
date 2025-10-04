provider "aws" {
  region = var.region
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

variable "scheduler_policy_name" {}
variable "scheduler_role_name" {}

module "nrds_orchestration" {
    source = "./modules/orchestration"

    region = var.region
    starter_lambda_name = var.starter_lambda_name
    commander_lambda_name = var.commander_lambda_name
    poller_lambda_name = var.poller_lambda_name
    checker_lambda_name = var.checker_lambda_name
    stopper_lambda_name = var.stopper_lambda_name
    lambda_policy_name = var.lambda_policy_name
    lambda_role_name = var.lambda_role_name
    lambda_invoke_policy_name = var.lambda_invoke_policy_name
    sm_name = var.sm_name
    sm_role_name = var.sm_role_name
    ec2_role = var.ec2_role
    ec2_policy_name = var.ec2_policy_name
    profile_name = var.profile_name
}

# module "nrds_schedules" {
#     source = "./modules/schedules"

#     region = var.region
#     scheduler_policy_name = var.scheduler_policy_name
#     scheduler_role_name = var.scheduler_role_name
# }

