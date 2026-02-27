output "short_range_schedule_count" {
  value = length(aws_scheduler_schedule.datastream_schedule_short_range_cfe_nom)
}

output "medium_range_schedule_count" {
  value = length(aws_scheduler_schedule.datastream_schedule_medium_range_cfe_nom)
}

output "analysis_assim_schedule_count" {
  value = length(aws_scheduler_schedule.datastream_schedule_AnA_range_cfe_nom)
}
