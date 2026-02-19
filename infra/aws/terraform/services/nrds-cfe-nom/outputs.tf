# Orchestration
output "datastream_arn" {
  value       = module.nrds_orchestration.datastream_arn
  description = "State machine ARN for the datastream workflow"
}

output "lambda_role_arn" {
  value       = module.nrds_orchestration.lambda_role_arn
  description = "IAM role ARN used by Lambda functions"
}

output "lambda_arns" {
  value       = module.nrds_orchestration.lambda_arns
  description = "ARNs of all Lambda functions in the orchestration workflow"
}

output "lambda_function_names" {
  value       = module.nrds_orchestration.lambda_function_names
  description = "Names of all Lambda functions in the orchestration workflow"
}

# Schedules
output "short_range_schedule_count" {
  value       = length(module.schedules.short_range_schedule_ids)
  description = "Number of short range CFE_NOM schedules created"
}

output "medium_range_schedule_count" {
  value       = length(module.schedules.medium_range_schedule_ids)
  description = "Number of medium range CFE_NOM schedules created"
}

output "analysis_assim_schedule_count" {
  value       = length(module.schedules.analysis_assim_schedule_ids)
  description = "Number of analysis/assimilation CFE_NOM schedules created"
}
