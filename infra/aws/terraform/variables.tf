variable "region" {
  type        = string
  description = "AWS region"
}

variable "resource_prefix" {
  type        = string
  description = "Prefix for resource naming (e.g., 'nrds_test', 'nrds_prod')"
}

variable "sm_name" {
  type        = string
  description = "Name of the Step Functions state machine"
}

variable "sm_role_name" {
  type        = string
  description = "Name of the IAM role for the state machine"
}

variable "starter_lambda_name" {
  type        = string
  description = "Name of the EC2 starter Lambda function"
}

variable "commander_lambda_name" {
  type        = string
  description = "Name of the EC2 commander Lambda function"
}

variable "poller_lambda_name" {
  type        = string
  description = "Name of the EC2 poller Lambda function"
}

variable "checker_lambda_name" {
  type        = string
  description = "Name of the S3 checker Lambda function"
}

variable "stopper_lambda_name" {
  type        = string
  description = "Name of the EC2 stopper Lambda function"
}

variable "lambda_policy_name" {
  type        = string
  description = "Name of the Lambda IAM policy"
}

variable "lambda_role_name" {
  type        = string
  description = "Name of the Lambda IAM role"
}

variable "lambda_invoke_policy_name" {
  type        = string
  description = "Name of the Lambda invoke policy for Step Functions"
}

variable "ec2_role" {
  type        = string
  description = "Name of the EC2 IAM role"
}

variable "ec2_policy_name" {
  type        = string
  description = "Name of the EC2 IAM policy"
}

variable "profile_name" {
  type        = string
  description = "Name of the EC2 instance profile"
}
