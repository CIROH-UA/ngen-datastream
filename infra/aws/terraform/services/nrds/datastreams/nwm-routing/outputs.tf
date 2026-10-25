output "nwm_routing_schedule_names" {
  value = [for s in aws_scheduler_schedule.nwm_routing_schedule : s.name]
}
