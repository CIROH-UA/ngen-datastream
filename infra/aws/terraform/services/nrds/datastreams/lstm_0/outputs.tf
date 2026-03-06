output "short_range_schedule_count" {
  value = length(aws_scheduler_schedule.datastream_schedule_short_range_lstm_0)
}

output "medium_range_schedule_count" {
  value = length(aws_scheduler_schedule.datastream_schedule_medium_range_lstm_0)
}

output "analysis_assim_schedule_count" {
  value = length(aws_scheduler_schedule.datastream_schedule_AnA_range_lstm_0)
}
