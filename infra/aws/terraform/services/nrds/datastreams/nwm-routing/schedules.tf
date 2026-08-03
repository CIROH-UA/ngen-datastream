locals {
  nwm_routing_config = jsondecode(file("${path.module}/config/execution_forecast_inputs_nwm_routing.json"))

  nwm_routing_template_path = "${path.module}/templates/execution_nwm_routing_VPU_template.json.tpl"

  nwm_routing_vpus = keys(local.nwm_routing_config.short_range.instance_types)

  nwm_routing_schedules = {
    for pair in flatten([
      for vpu in local.nwm_routing_vpus : [
        for init in local.nwm_routing_config.short_range.init_cycles : {
          key           = "${init}_${vpu}"
          init          = init
          vpu           = vpu
          instance_type = local.nwm_routing_config.short_range.instance_types[vpu]
          volume_size   = local.nwm_routing_config.short_range.volume_size
          timeout_s     = local.nwm_routing_config.short_range.timeout_s
          # N_CPUS handed to t-route; keep <= vCPUs of the instance type above
          nprocs = 4
        }
      ]
    ]) : pair.key => pair
  }

  # Fire at (init + 1):00 in schedule_timezone — mirrors routing-only, which is
  # late enough for the NWM cycle's CHRTOUT files to be on GCS.
  nwm_routing_times = {
    for k, v in local.nwm_routing_schedules : k => (tonumber(v.init) + 1) % 24
  }
}

resource "aws_scheduler_schedule" "nwm_routing_schedule" {
  for_each = local.nwm_routing_schedules

  name       = "short_range_fcst${each.value.init}_vpu${each.value.vpu}_schedule_nwm_routing_${var.environment_suffix}"
  group_name = var.schedule_group_name

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 ${local.nwm_routing_times[each.key]} * * ? *)"
  schedule_expression_timezone = var.schedule_timezone

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:sfn:startExecution"
    role_arn = var.scheduler_role_arn
    input    = <<-EOT
{
  "StateMachineArn": "${var.state_machine_arn}",
  "Name": "nwm_routing_short_range_vpu${each.value.vpu}_init${each.value.init}_<aws.scheduler.execution-id>",
  "Input": ${jsonencode(templatefile(local.nwm_routing_template_path, {
    init               = each.value.init
    vpu                = each.value.vpu
    nprocs             = each.value.nprocs
    ami_id             = var.ami_id
    instance_type      = each.value.instance_type
    instance_profile   = var.ec2_instance_profile
    volume_size        = each.value.volume_size
    timeout_s          = each.value.timeout_s
    environment_suffix = var.environment_suffix
    s3_bucket          = var.s3_bucket
    preprocess_image   = local.nwm_routing_config.images.preprocess
    postprocess_image  = local.nwm_routing_config.images.postprocess
    routing_image      = local.nwm_routing_config.images.routing
}))}
}
EOT
  }
}
