# State Machine
output "datastream_arn" {
  value       = module.orchestration.datastream_arn
  description = "State machine ARN for the datastream workflow"
}

# Security
output "ec2_security_group_id" {
  value       = module.orchestration.ec2_security_group_id
  description = "Security group ID for EC2 instances"
}

# EC2 Instance Profile
output "ec2_instance_profile_name" {
  value       = module.orchestration.ec2_instance_profile_name
  description = "IAM instance profile name for EC2 instances"
}

# Lambda Functions
output "lambda_role_arn" {
  value       = module.orchestration.lambda_role_arn
  description = "IAM role ARN used by Lambda functions"
}

output "lambda_arns" {
  value       = module.orchestration.lambda_arns
  description = "ARNs of all Lambda functions in the orchestration workflow"
}

output "lambda_function_names" {
  value       = module.orchestration.lambda_function_names
  description = "Names of all Lambda functions in the orchestration workflow"
}

# Write ARN to file for external reference
resource "local_file" "write_arn" {
  content  = module.orchestration.datastream_arn
  filename = "${path.module}/sm_ARN.txt"
}
