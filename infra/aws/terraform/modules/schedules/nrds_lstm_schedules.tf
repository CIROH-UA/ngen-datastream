# Terraform configuration for AWS Scheduler to trigger Step Functions executions for NRDS LSTM
# Uses templatefile() for dynamic execution JSON generation - no pre-generated files needed

locals {
  init_cycles_config_lstm = jsondecode(file("${path.module}/config/execution_forecast_inputs_lstm.json"))

  # LSTM template path
  lstm_template_path = "${path.module}/executions/templates/execution_datastream_lstm_VPU_template.json.tpl"

  # Common LSTM configuration
  lstm_ami_id           = "ami-0bba768785947ef54"
  lstm_key_name         = "jlaser_community_east1"
  lstm_security_groups  = jsonencode(["sg-0fcbe0c6d6faa0117"])
  lstm_instance_profile = "datastream_community_ec2_profile"

  # Short range forecast config mapping
  short_range_lstm_config = {
    for pair in flatten([
      for init in local.init_cycles_config_lstm.short_range.init_cycles : [
        for vpu in local.vpus : {
          key           = "${init}_${vpu}"
          init          = init
          vpu           = vpu
          instance_type = local.init_cycles_config_lstm.short_range.instance_types[vpu]
          volume_size   = local.init_cycles_config_lstm.short_range.volume_size
          run_type_l    = "short_range"
          run_type_h    = "SHORT_RANGE"
          fcst          = "f001_f018"
          member        = ""
          member_suffix = ""
          member_path   = ""
          nprocs        = 3
          timeout_s     = 3600
        }
      ]
    ]) : pair.key => pair
  }

  short_range_times_lstm = {
    for pair in flatten([
      for init in local.init_cycles_config_lstm.short_range.init_cycles : [
        for vpu in local.vpus : {
          key   = "${init}_${vpu}"
          value = vpu == "fp" ? (tonumber(init)) % 24 : (tonumber(init) + 1) % 24
        }
      ]
    ]) : pair.key => pair.value
  }

  # Medium range forecast config mapping
  medium_range_lstm_config = {
    for pair in flatten([
      for init in local.init_cycles_config_lstm.medium_range.init_cycles : [
        for vpu in local.vpus : [
          for member in(
            vpu == "fp" ? ["1"] : local.init_cycles_config_lstm.medium_range.ensemble_members
            ) : {
            key           = "${init}_${member}_${vpu}"
            init          = init
            vpu           = vpu
            instance_type = local.init_cycles_config_lstm.medium_range.instance_types[vpu]
            volume_size   = local.init_cycles_config_lstm.medium_range.volume_size
            run_type_l    = "medium_range"
            run_type_h    = "MEDIUM_RANGE"
            fcst          = "f001_f240"
            member        = member
            member_suffix = "_${member}"
            member_path   = "/${member}"
            nprocs        = 7
            timeout_s     = 7200
          }
        ]
      ]
    ]) : pair.key => pair
  }

  medium_range_times_lstm = {
    for pair in flatten([
      for init in local.init_cycles_config_lstm.medium_range.init_cycles : [
        for vpu in local.vpus : [
          for member in(
            vpu == "fp" ? ["1"] : local.init_cycles_config_lstm.medium_range.ensemble_members
            ) : {
            key   = "${init}_${member}_${vpu}"
            value = vpu == "fp" ? (tonumber(init) + 2) % 24 : (tonumber(init) + 3) % 24
          }
        ]
      ]
    ]) : pair.key => pair.value
  }

  medium_range_member_offsets_lstm = {
    for pair in flatten([
      for init in local.init_cycles_config_lstm.medium_range.init_cycles : [
        for member in local.init_cycles_config_lstm.medium_range.ensemble_members : [
          for vpu in local.vpus : {
            key   = "${init}_${member}_${vpu}"
            value = floor(((tonumber(member) - 1) * (1.0 / 7.0) * 60) % 60)
          }
        ]
      ]
    ]) : pair.key => pair.value
  }

  # Analysis/Assimilation forecast config mapping
  analysis_assim_extend_lstm_config = {
    for pair in flatten([
      for init in local.init_cycles_config_lstm.analysis_assim_extend.init_cycles : [
        for vpu in local.vpus : {
          key           = "${init}_${vpu}"
          init          = init
          vpu           = vpu
          instance_type = local.init_cycles_config_lstm.analysis_assim_extend.instance_types[vpu]
          volume_size   = local.init_cycles_config_lstm.analysis_assim_extend.volume_size
          run_type_l    = "analysis_assim_extend"
          run_type_h    = "ANALYSIS_ASSIM_EXTEND"
          fcst          = "tm27_tm00"
          member        = ""
          member_suffix = ""
          member_path   = ""
          nprocs        = 3
          timeout_s     = 3600
        }
      ]
    ]) : pair.key => pair
  }

  analysis_assim_extend_times_lstm = {
    for pair in flatten([
      for init in local.init_cycles_config_lstm.analysis_assim_extend.init_cycles : [
        for vpu in local.vpus : {
          key   = "${init}_${vpu}"
          value = vpu == "fp" ? 15 : 16
        }
      ]
    ]) : pair.key => pair.value
  }
}

# Short Range LSTM Schedules
resource "aws_scheduler_schedule" "datastream_schedule_short_range_lstm" {
  for_each = local.short_range_lstm_config

  name       = "short_range_fcst${each.value.init}_vpu${each.value.vpu}_schedule_lstm_test"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 ${local.short_range_times_lstm[each.key]} * * ? *)"
  schedule_expression_timezone = "America/New_York"

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:sfn:startExecution"
    role_arn = aws_iam_role.scheduler_role.arn
    input    = <<-EOT
{
  "StateMachineArn": "${var.state_machine_arn}",
  "Name": "lstm_short_range_vpu${each.value.vpu}_init${each.value.init}_<aws.scheduler.execution-id>",
  "Input": ${jsonencode(templatefile(local.lstm_template_path, {
    vpu                = each.value.vpu
    init               = each.value.init
    run_type_l         = each.value.run_type_l
    run_type_h         = each.value.run_type_h
    fcst               = each.value.fcst
    member             = each.value.member
    member_suffix      = each.value.member_suffix
    member_path        = each.value.member_path
    nprocs             = each.value.nprocs
    timeout_s          = each.value.timeout_s
    ami_id             = local.lstm_ami_id
    instance_type      = each.value.instance_type
    key_name           = local.lstm_key_name
    security_group_ids = local.lstm_security_groups
    instance_profile   = local.lstm_instance_profile
    volume_size        = each.value.volume_size
  }))}
}
EOT
  }
}

# Medium Range LSTM Schedules
resource "aws_scheduler_schedule" "datastream_schedule_medium_range_lstm" {
  for_each = local.medium_range_lstm_config

  name       = "medium_range_fcst${each.value.init}_mem${each.value.member}_vpu${each.value.vpu}_schedule_lstm_test"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(${local.medium_range_member_offsets_lstm[each.key]} ${local.medium_range_times_lstm[each.key]} * * ? *)"
  schedule_expression_timezone = "America/New_York"

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:sfn:startExecution"
    role_arn = aws_iam_role.scheduler_role.arn
    input    = <<-EOT
{
  "StateMachineArn": "${var.state_machine_arn}",
  "Name": "lstm_medium_range_vpu${each.value.vpu}_init${each.value.init}_mem${each.value.member}_<aws.scheduler.execution-id>",
  "Input": ${jsonencode(templatefile(local.lstm_template_path, {
    vpu                = each.value.vpu
    init               = each.value.init
    run_type_l         = each.value.run_type_l
    run_type_h         = each.value.run_type_h
    fcst               = each.value.fcst
    member             = each.value.member
    member_suffix      = each.value.member_suffix
    member_path        = each.value.member_path
    nprocs             = each.value.nprocs
    timeout_s          = each.value.timeout_s
    ami_id             = local.lstm_ami_id
    instance_type      = each.value.instance_type
    key_name           = local.lstm_key_name
    security_group_ids = local.lstm_security_groups
    instance_profile   = local.lstm_instance_profile
    volume_size        = each.value.volume_size
  }))}
}
EOT
  }
}

# Analysis/Assimilation LSTM Schedules
resource "aws_scheduler_schedule" "datastream_schedule_AnA_range_lstm" {
  for_each = local.analysis_assim_extend_lstm_config

  name       = "analysis_assim_extend_fcst${each.value.init}_vpu${each.value.vpu}_schedule_lstm_test"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 ${local.analysis_assim_extend_times_lstm[each.key]} * * ? *)"
  schedule_expression_timezone = "America/New_York"

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:sfn:startExecution"
    role_arn = aws_iam_role.scheduler_role.arn
    input    = <<-EOT
{
  "StateMachineArn": "${var.state_machine_arn}",
  "Name": "lstm_analysis_assim_vpu${each.value.vpu}_init${each.value.init}_<aws.scheduler.execution-id>",
  "Input": ${jsonencode(templatefile(local.lstm_template_path, {
    vpu                = each.value.vpu
    init               = each.value.init
    run_type_l         = each.value.run_type_l
    run_type_h         = each.value.run_type_h
    fcst               = each.value.fcst
    member             = each.value.member
    member_suffix      = each.value.member_suffix
    member_path        = each.value.member_path
    nprocs             = each.value.nprocs
    timeout_s          = each.value.timeout_s
    ami_id             = local.lstm_ami_id
    instance_type      = each.value.instance_type
    key_name           = local.lstm_key_name
    security_group_ids = local.lstm_security_groups
    instance_profile   = local.lstm_instance_profile
    volume_size        = each.value.volume_size
  }))}
}
EOT
  }
}
