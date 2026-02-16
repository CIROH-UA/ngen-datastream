output "short_range_schedule_count" {
  value       = length(module.schedules.short_range_schedule_ids)
  description = "Number of short range routing-only schedules created"
}
