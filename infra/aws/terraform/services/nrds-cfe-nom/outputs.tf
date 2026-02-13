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
