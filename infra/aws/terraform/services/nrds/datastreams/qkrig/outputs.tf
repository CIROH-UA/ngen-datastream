output "qkrig_daily_schedule_names" {
  value = [for s in aws_scheduler_schedule.qkrig_daily_schedule : s.name]
}
