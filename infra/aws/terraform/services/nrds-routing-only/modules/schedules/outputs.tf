output "short_range_schedule_ids" {
  value       = [for s in aws_scheduler_schedule.datastream_schedule_short_range_routing_only : s.id]
  description = "IDs of short range routing-only schedules"
}
