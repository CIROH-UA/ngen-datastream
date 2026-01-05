terraform {
  required_version = ">= 0.12"
}

variable "region" {}
variable "scheduler_policy_name" {}
variable "scheduler_role_name" {}

data "aws_ssm_parameter" "state_machine_arn" {
  name            = "/datastream/test/state-machine-arn"
  with_decryption = true
}