locals {
  restart_config = jsondecode(file("${path.module}/config/execution_forecast_inputs_restart.json"))

  restart_template_path = "${path.module}/templates/execution_restart_template.json.tpl"
  restart_vpu_list      = "01,02,03N,03S,03W,04,05,06,07,08,09,10L,10U,11,12,13,14,15,16,18"

  restart_schedules = {
    for init in local.restart_config.init_cycles : init => {
      init          = init
      instance_type = local.restart_config.instance_type
      volume_size   = local.restart_config.volume_size
      timeout_s     = local.restart_config.timeout_s
    }
  }

  # Run 30 minutes before routing-only (which runs at init+1 hour)
  # So restart runs at init hour :30
  restart_times = {
    for init in local.restart_config.init_cycles : init => tonumber(init)
  }
}

resource "aws_scheduler_schedule" "restart_schedule" {
  for_each = local.restart_schedules

  name       = "restart_init${each.value.init}_schedule_${var.environment_suffix}"
  group_name = var.schedule_group_name

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(30 ${local.restart_times[each.key]} * * ? *)"
  schedule_expression_timezone = var.schedule_timezone

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:sfn:startExecution"
    role_arn = var.scheduler_role_arn
    input = <<-EOT
{
  "StateMachineArn": "${var.state_machine_arn}",
  "Name": "restart_init${each.value.init}_<aws.scheduler.execution-id>",
  "Input": ${jsonencode(templatefile(local.restart_template_path, {
    init               = each.value.init
    ami_id             = var.restart_ami_id
    instance_type      = each.value.instance_type
    instance_profile   = var.ec2_instance_profile
    volume_size        = each.value.volume_size
    timeout_s          = each.value.timeout_s
    environment_suffix = var.environment_suffix
    s3_bucket          = var.s3_bucket
    ds_tag             = var.ds_tag
    fp_tag             = var.fp_tag
    vpu_list           = local.restart_vpu_list
  }))}
}
EOT
  }
}
