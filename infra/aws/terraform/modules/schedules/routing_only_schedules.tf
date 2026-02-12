# Terraform configuration for AWS Scheduler to trigger Step Functions executions
# for Routing-Only forecasts
# Uses templatefile() for dynamic execution JSON generation - no pre-generated files needed

locals {
  init_cycles_config_routing_only = jsondecode(file("${path.module}/config/execution_forecast_inputs_routing_only.json"))

  # Routing-Only template path
  routing_only_template_path = "${path.module}/executions/templates/execution_datastream_routing_only_VPU_template.json.tpl"

  # Routing-Only VPUs (currently only 03W)
  routing_only_vpus = keys(local.init_cycles_config_routing_only.short_range.instance_types)

  # Common Routing-Only configuration
  routing_only_ami_id           = var.routing_only_ami_id
  routing_only_security_groups  = jsonencode(var.ec2_security_groups)
  routing_only_instance_profile = var.ec2_instance_profile

  # Short range forecast config mapping
  short_range_routing_only_config = {
    for pair in flatten([
      for init in local.init_cycles_config_routing_only.short_range.init_cycles : [
        for vpu in local.routing_only_vpus : {
          key           = "${init}_${vpu}"
          init          = init
          vpu           = vpu
          instance_type = local.init_cycles_config_routing_only.short_range.instance_types[vpu]
          volume_size   = local.init_cycles_config_routing_only.short_range.volume_size
          run_type_l    = "short_range"
          run_type_h    = "SHORT_RANGE"
          nprocs        = 4
        }
      ]
    ]) : pair.key => pair
  }

  short_range_times_routing_only = {
    for pair in flatten([
      for init in local.init_cycles_config_routing_only.short_range.init_cycles : [
        for vpu in local.routing_only_vpus : {
          key   = "${init}_${vpu}"
          value = (tonumber(init) + 1) % 24
        }
      ]
    ]) : pair.key => pair.value
  }
}

# Short Range Routing-Only Schedules
resource "aws_scheduler_schedule" "datastream_schedule_short_range_routing_only" {
  for_each = local.short_range_routing_only_config

  name       = "short_range_fcst${each.value.init}_vpu${each.value.vpu}_schedule_routing_only_${var.environment_suffix}"
  group_name = var.schedule_group_name

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 ${local.short_range_times_routing_only[each.key]} * * ? *)"
  schedule_expression_timezone = var.schedule_timezone

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:sfn:startExecution"
    role_arn = aws_iam_role.scheduler_role.arn
    input = <<-EOT
{
  "StateMachineArn": "${var.state_machine_arn}",
  "Name": "routing_only_short_range_vpu${each.value.vpu}_init${each.value.init}_<aws.scheduler.execution-id>",
  "Input": ${jsonencode(templatefile(local.routing_only_template_path, {
    vpu                = each.value.vpu
    init               = each.value.init
    run_type_l         = each.value.run_type_l
    run_type_h         = each.value.run_type_h
    nprocs             = each.value.nprocs
    ami_id             = local.routing_only_ami_id
    instance_type      = each.value.instance_type
    security_group_ids = local.routing_only_security_groups
    instance_profile   = local.routing_only_instance_profile
    volume_size        = each.value.volume_size
    environment_suffix = var.environment_suffix
  }))}
}
EOT
  }
}