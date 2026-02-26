output "datastream_arn" {
  value = module.nrds_orchestration.datastream_arn
}

output "lambda_role_arn" {
  value = module.nrds_orchestration.lambda_role_arn
}

output "lambda_arns" {
  value = module.nrds_orchestration.lambda_arns
}

output "lambda_function_names" {
  value = module.nrds_orchestration.lambda_function_names
}

output "ec2_instance_profile_name" {
  value = module.nrds_orchestration.ec2_instance_profile_name
}

output "routing_only_short_range_schedule_count" {
  value = module.routing_only_schedules.short_range_schedule_count
}
