locals {
  qkrig_config = jsondecode(file("${path.module}/config/execution_forecast_inputs_qkrig.json"))

  qkrig_template_path = "${path.module}/templates/execution_qkrig_daily_template.json.tpl"

  qkrig_daily_schedules = {
    for init in local.qkrig_config.init_cycles : init => {
      init          = init
      instance_type = local.qkrig_config.instance_type
      volume_size   = local.qkrig_config.volume_size
      timeout_s     = local.qkrig_config.timeout_s
    }
  }
}

resource "aws_scheduler_schedule" "qkrig_daily_schedule" {
  for_each = local.qkrig_daily_schedules

  name       = "qkrig_init${each.value.init}_schedule_${var.environment_suffix}"
  group_name = var.schedule_group_name

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(30 ${tonumber(each.value.init) % 24} * * ? *)"
  schedule_expression_timezone = var.schedule_timezone

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:sfn:startExecution"
    role_arn = var.scheduler_role_arn
    input = <<-EOT
{
  "StateMachineArn": "${var.state_machine_arn}",
  "Name": "qkrig_init${each.value.init}_<aws.scheduler.execution-id>",
  "Input": ${jsonencode(templatefile(local.qkrig_template_path, {
    init               = each.value.init
    ami_id             = var.qkrig_ami_id
    instance_type      = each.value.instance_type
    instance_profile   = var.ec2_instance_profile
    volume_size        = each.value.volume_size
    timeout_s          = each.value.timeout_s
    environment_suffix = var.environment_suffix
    s3_bucket          = var.s3_bucket
}))}
}
EOT
}
}
