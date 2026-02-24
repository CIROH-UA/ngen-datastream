output "short_range_schedule_ids" {
  value       = [for s in aws_scheduler_schedule.datastream_schedule_short_range_cfe_nom : s.id]
  description = "IDs of short range CFE_NOM schedules"
}

output "medium_range_schedule_ids" {
  value       = [for s in aws_scheduler_schedule.datastream_schedule_medium_range_cfe_nom : s.id]
  description = "IDs of medium range CFE_NOM schedules"
}

output "analysis_assim_schedule_ids" {
  value       = [for s in aws_scheduler_schedule.datastream_schedule_AnA_range_cfe_nom : s.id]
  description = "IDs of analysis/assimilation CFE_NOM schedules"
}
