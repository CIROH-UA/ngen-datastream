# Terraform configuration for AWS Scheduler to trigger Step Functions executions
# for Routing-Only Short Range forecasts (VPU_03W only)

locals {
  routing_only_init_cycles = [
    "00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11",
    "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23"
  ]

  routing_only_paths = {
    for init in local.routing_only_init_cycles :
    init => "${path.module}/executions/routing_only/short_range/execution_routing_only_${init}.json"
  }

  # Schedule 1 hour after init cycle (e.g., 00z runs at 01:00 UTC)
  routing_only_times = {
    for init in local.routing_only_init_cycles :
    init => (tonumber(init) + 1) % 24
  }
}

resource "aws_scheduler_schedule" "routing_only_short_range" {
  for_each = local.routing_only_paths

  name       = "routing_only_short_range_${each.key}_vpu03w_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 ${local.routing_only_times[each.key]} * * ? *)"
  schedule_expression_timezone = "America/New_York"

  target {
    arn      = data.aws_ssm_parameter.state_machine_arn.value
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file(each.value)
  }
}
