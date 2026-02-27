output "short_range_schedule_count" {
  value = length(aws_scheduler_schedule.datastream_schedule_short_range_routing_only)
}
