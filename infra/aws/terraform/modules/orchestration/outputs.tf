output "datastream_arn" {
  value       = aws_sfn_state_machine.datastream_state_machine.arn
  description = "State machine ARN for the datastream workflow"
}

output "lambda_role_arn" {
  value       = aws_iam_role.lambda_role.arn
  description = "IAM role ARN used by Lambda functions"
}

output "lambda_arns" {
  value = [
    aws_lambda_function.starter_lambda.arn,
    aws_lambda_function.commander_lambda.arn,
    aws_lambda_function.poller_lambda.arn,
    aws_lambda_function.checker_lambda.arn,
    aws_lambda_function.stopper_lambda.arn
  ]
  description = "ARNs of all Lambda functions in the orchestration workflow"
}

output "ec2_instance_profile_name" {
  value       = aws_iam_instance_profile.instance_profile.name
  description = "IAM instance profile name for EC2 instances"
}

output "lambda_function_names" {
  value = [
    aws_lambda_function.starter_lambda.function_name,
    aws_lambda_function.commander_lambda.function_name,
    aws_lambda_function.poller_lambda.function_name,
    aws_lambda_function.checker_lambda.function_name,
    aws_lambda_function.stopper_lambda.function_name
  ]
  description = "Names of all Lambda functions in the orchestration workflow"
}

resource "local_file" "write_arn" {
  content  = aws_sfn_state_machine.datastream_state_machine.arn
  filename = "${path.module}/sm_ARN.txt"
}
