provider "aws" {
  region = var.region
}

terraform {
  required_version = ">= 0.12"
}
#checkov:skip=CKV_AWS_337:Using AWS-managed key is acceptable for state machine ARN reference
resource "aws_ssm_parameter" "state_machine_arn" {
  name  = var.sm_parameter_name
  type  = "SecureString"
  value = aws_sfn_state_machine.datastream_state_machine.arn
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
variable "sm_parameter_name" {
  default = "/datastream/state-machine-arn"
}
variable "ec2_role" {}
variable "ec2_policy_name" {}
variable "profile_name" {}
