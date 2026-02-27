locals {
  init_cycles_config_forcing = jsondecode(file("${path.module}/config/execution_forecast_inputs_forcing.json"))

  fp_template_path = "${path.module}/templates/execution_forcing_template.json.tpl"
  fp_vpu_list      = "01,02,03N,03S,03W,04,05,06,07,08,09,10L,10U,11,12,13,14,15,16,18"

  short_range_forcing_config = {
    for init in local.init_cycles_config_forcing.short_range.init_cycles : init => {
      init          = init
      instance_type = local.init_cycles_config_forcing.short_range.instance_type
      volume_size   = local.init_cycles_config_forcing.short_range.volume_size
      run_type_l    = "short_range"
      run_type_h    = "SHORT_RANGE"
      member_suffix = ""
    }
  }

  medium_range_forcing_config = {
    for init in local.init_cycles_config_forcing.medium_range.init_cycles : init => {
      init          = init
      instance_type = local.init_cycles_config_forcing.medium_range.instance_type
      volume_size   = local.init_cycles_config_forcing.medium_range.volume_size
      run_type_l    = "medium_range"
      run_type_h    = "MEDIUM_RANGE"
      member_suffix = "_0"
    }
  }

  analysis_assim_extend_forcing_config = {
    for init in local.init_cycles_config_forcing.analysis_assim_extend.init_cycles : init => {
      init          = init
      instance_type = local.init_cycles_config_forcing.analysis_assim_extend.instance_type
      volume_size   = local.init_cycles_config_forcing.analysis_assim_extend.volume_size
      run_type_l    = "analysis_assim_extend"
      run_type_h    = "ANALYSIS_ASSIM_EXTEND"
      member_suffix = ""
    }
  }
}

# Short Range Forcing Schedules
resource "aws_scheduler_schedule" "datastream_schedule_short_range_forcing" {
  for_each = local.short_range_forcing_config

  name       = "short_range_fcst${each.value.init}_forcing_schedule_${var.environment_suffix}"
  group_name = var.schedule_group_name

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 ${tonumber(each.value.init) % 24} * * ? *)"
  schedule_expression_timezone = var.schedule_timezone

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:sfn:startExecution"
    role_arn = var.scheduler_role_arn
    input = <<-EOT
{
  "StateMachineArn": "${var.state_machine_arn}",
  "Name": "forcing_short_range_init${each.value.init}_<aws.scheduler.execution-id>",
  "Input": ${jsonencode(templatefile(local.fp_template_path, {
    init               = each.value.init
    run_type_l         = each.value.run_type_l
    run_type_h         = each.value.run_type_h
    member_suffix      = each.value.member_suffix
    ami_id             = var.fp_ami_id
    instance_type      = each.value.instance_type
    instance_profile   = var.ec2_instance_profile
    volume_size        = each.value.volume_size
    timeout_s          = 3600
    environment_suffix = var.environment_suffix
    s3_bucket          = var.s3_bucket
    vpu_list           = local.fp_vpu_list
}))}
}
EOT
}
}

# Medium Range Forcing Schedules
resource "aws_scheduler_schedule" "datastream_schedule_medium_range_forcing" {
  for_each = local.medium_range_forcing_config

  name       = "medium_range_fcst${each.value.init}_forcing_schedule_${var.environment_suffix}"
  group_name = var.schedule_group_name

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 ${(tonumber(each.value.init) + 2) % 24} * * ? *)"
  schedule_expression_timezone = var.schedule_timezone

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:sfn:startExecution"
    role_arn = var.scheduler_role_arn
    input = <<-EOT
{
  "StateMachineArn": "${var.state_machine_arn}",
  "Name": "forcing_medium_range_init${each.value.init}_<aws.scheduler.execution-id>",
  "Input": ${jsonencode(templatefile(local.fp_template_path, {
    init               = each.value.init
    run_type_l         = each.value.run_type_l
    run_type_h         = each.value.run_type_h
    member_suffix      = each.value.member_suffix
    ami_id             = var.fp_ami_id
    instance_type      = each.value.instance_type
    instance_profile   = var.ec2_instance_profile
    volume_size        = each.value.volume_size
    timeout_s          = 7200
    environment_suffix = var.environment_suffix
    s3_bucket          = var.s3_bucket
    vpu_list           = local.fp_vpu_list
}))}
}
EOT
}
}

# Analysis/Assimilation Forcing Schedules
resource "aws_scheduler_schedule" "datastream_schedule_AnA_range_forcing" {
  for_each = local.analysis_assim_extend_forcing_config

  name       = "analysis_assim_extend_fcst${each.value.init}_forcing_schedule_${var.environment_suffix}"
  group_name = var.schedule_group_name

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 ${(tonumber(each.value.init) + 23) % 24} * * ? *)"
  schedule_expression_timezone = var.schedule_timezone

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:sfn:startExecution"
    role_arn = var.scheduler_role_arn
    input = <<-EOT
{
  "StateMachineArn": "${var.state_machine_arn}",
  "Name": "forcing_analysis_assim_extend_init${each.value.init}_<aws.scheduler.execution-id>",
  "Input": ${jsonencode(templatefile(local.fp_template_path, {
    init               = each.value.init
    run_type_l         = each.value.run_type_l
    run_type_h         = each.value.run_type_h
    member_suffix      = each.value.member_suffix
    ami_id             = var.fp_ami_id
    instance_type      = each.value.instance_type
    instance_profile   = var.ec2_instance_profile
    volume_size        = each.value.volume_size
    timeout_s          = 3600
    environment_suffix = var.environment_suffix
    s3_bucket          = var.s3_bucket
    vpu_list           = local.fp_vpu_list
}))}
}
EOT
}
}
