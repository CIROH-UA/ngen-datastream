output "restart_schedule_names" {
  value = [for s in aws_scheduler_schedule.restart_schedule : s.name]
}
