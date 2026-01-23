# Terraform configuration for AWS Scheduler to trigger Step Functions executions for NRDS CFE_NOM
# Uses templatefile() for dynamic execution JSON generation - no pre-generated files needed

locals {
  init_cycles_config_cfe_nom = jsondecode(file("${path.module}/config/execution_forecast_inputs_cfe_nom.json"))

  # CFE_NOM template path
  cfe_nom_template_path = "${path.module}/executions/templates/execution_datastream_cfe_nom_VPU_template.json.tpl"

  # Common CFE_NOM configuration
  cfe_nom_ami_id           = "ami-0ef008a1e6d9aa12d"
  cfe_nom_key_name         = "jlaser_community_east1"
  cfe_nom_security_groups  = jsonencode(["sg-0fcbe0c6d6faa0117"])
  cfe_nom_instance_profile = "datastream_community_ec2_profile"

  # Short range forecast config mapping
  short_range_cfe_nom_config = {
    for pair in flatten([
      for init in local.init_cycles_config_cfe_nom.short_range.init_cycles : [
        for vpu in local.vpus : {
          key           = "${init}_${vpu}"
          init          = init
          vpu           = vpu
          instance_type = local.init_cycles_config_cfe_nom.short_range.instance_types[vpu]
          volume_size   = local.init_cycles_config_cfe_nom.short_range.volume_size
          run_type_l    = "short_range"
          run_type_h    = "SHORT_RANGE"
          fcst          = "f001_f018"
          member        = ""
          member_suffix = ""
          member_path   = ""
          nprocs        = 3
        }
      ]
    ]) : pair.key => pair
  }

  short_range_times_cfe_nom = {
    for pair in flatten([
      for init in local.init_cycles_config_cfe_nom.short_range.init_cycles : [
        for vpu in local.vpus : {
          key   = "${init}_${vpu}"
          value = vpu == "fp" ? (tonumber(init)) % 24 : (tonumber(init) + 1) % 24
        }
      ]
    ]) : pair.key => pair.value
  }

  # Medium range forecast config mapping
  medium_range_cfe_nom_config = {
    for pair in flatten([
      for init in local.init_cycles_config_cfe_nom.medium_range.init_cycles : [
        for vpu in local.vpus : [
          for member in(
            vpu == "fp" ? ["1"] : local.init_cycles_config_cfe_nom.medium_range.ensemble_members
            ) : {
            key           = "${init}_${member}_${vpu}"
            init          = init
            vpu           = vpu
            instance_type = local.init_cycles_config_cfe_nom.medium_range.instance_types[vpu]
            volume_size   = local.init_cycles_config_cfe_nom.medium_range.volume_size
            run_type_l    = "medium_range"
            run_type_h    = "MEDIUM_RANGE"
            fcst          = "f001_f240"
            member        = member
            member_suffix = "_${member}"
            member_path   = "/${member}"
            nprocs        = 3
          }
        ]
      ]
    ]) : pair.key => pair
  }

  medium_range_times_cfe_nom = {
    for pair in flatten([
      for init in local.init_cycles_config_cfe_nom.medium_range.init_cycles : [
        for vpu in local.vpus : [
          for member in(
            vpu == "fp" ? ["1"] : local.init_cycles_config_cfe_nom.medium_range.ensemble_members
            ) : {
            key   = "${init}_${member}_${vpu}"
            value = vpu == "fp" ? (tonumber(init) + 2) % 24 : (tonumber(init) + 3) % 24
          }
        ]
      ]
    ]) : pair.key => pair.value
  }

  medium_range_member_offsets_cfe_nom = {
    for pair in flatten([
      for init in local.init_cycles_config_cfe_nom.medium_range.init_cycles : [
        for member in local.init_cycles_config_cfe_nom.medium_range.ensemble_members : [
          for vpu in local.vpus : {
            key   = "${init}_${member}_${vpu}"
            value = floor(((tonumber(member) - 1) * (1.0 / 7.0) * 60) % 60)
          }
        ]
      ]
    ]) : pair.key => pair.value
  }

  # Analysis/Assimilation forecast config mapping
  analysis_assim_extend_cfe_nom_config = {
    for pair in flatten([
      for init in local.init_cycles_config_cfe_nom.analysis_assim_extend.init_cycles : [
        for vpu in local.vpus : {
          key           = "${init}_${vpu}"
          init          = init
          vpu           = vpu
          instance_type = local.init_cycles_config_cfe_nom.analysis_assim_extend.instance_types[vpu]
          volume_size   = local.init_cycles_config_cfe_nom.analysis_assim_extend.volume_size
          run_type_l    = "analysis_assim_extend"
          run_type_h    = "ANALYSIS_ASSIM_EXTEND"
          fcst          = "f001_f028"
          member        = ""
          member_suffix = ""
          member_path   = ""
          nprocs        = 3
        }
      ]
    ]) : pair.key => pair
  }

  analysis_assim_extend_times_cfe_nom = {
    for pair in flatten([
      for init in local.init_cycles_config_cfe_nom.analysis_assim_extend.init_cycles : [
        for vpu in local.vpus : {
          key   = "${init}_${vpu}"
          value = vpu == "fp" ? 15 : 16
        }
      ]
    ]) : pair.key => pair.value
  }
}

# Short Range CFE_NOM Schedules
resource "aws_scheduler_schedule" "datastream_schedule_short_range_cfe_nom" {
  for_each = local.short_range_cfe_nom_config

  name       = "short_range_fcst${each.value.init}_vpu${each.value.vpu}_schedule_cfe_nom_test"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 ${local.short_range_times_cfe_nom[each.key]} * * ? *)"
  schedule_expression_timezone = "America/New_York"

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:sfn:startExecution"
    role_arn = aws_iam_role.scheduler_role.arn
    input    = <<-EOT
{
  "StateMachineArn": "${var.state_machine_arn}",
  "Name": "cfe_nom_short_range_vpu${each.value.vpu}_init${each.value.init}_<aws.scheduler.execution-id>",
  "Input": ${jsonencode(templatefile(local.cfe_nom_template_path, {
    vpu                = each.value.vpu
    init               = each.value.init
    run_type_l         = each.value.run_type_l
    run_type_h         = each.value.run_type_h
    fcst               = each.value.fcst
    member             = each.value.member
    member_suffix      = each.value.member_suffix
    member_path        = each.value.member_path
    nprocs             = each.value.nprocs
    ami_id             = local.cfe_nom_ami_id
    instance_type      = each.value.instance_type
    key_name           = local.cfe_nom_key_name
    security_group_ids = local.cfe_nom_security_groups
    instance_profile   = local.cfe_nom_instance_profile
    volume_size        = each.value.volume_size
  }))}
}
EOT
  }
}

# Medium Range CFE_NOM Schedules
resource "aws_scheduler_schedule" "datastream_schedule_medium_range_cfe_nom" {
  for_each = local.medium_range_cfe_nom_config

  name       = "medium_range_fcst${each.value.init}_mem${each.value.member}_vpu${each.value.vpu}_schedule_cfe_nom_test"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(${local.medium_range_member_offsets_cfe_nom[each.key]} ${local.medium_range_times_cfe_nom[each.key]} * * ? *)"
  schedule_expression_timezone = "America/New_York"

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:sfn:startExecution"
    role_arn = aws_iam_role.scheduler_role.arn
    input    = <<-EOT
{
  "StateMachineArn": "${var.state_machine_arn}",
  "Name": "cfe_nom_medium_range_vpu${each.value.vpu}_init${each.value.init}_mem${each.value.member}_<aws.scheduler.execution-id>",
  "Input": ${jsonencode(templatefile(local.cfe_nom_template_path, {
    vpu                = each.value.vpu
    init               = each.value.init
    run_type_l         = each.value.run_type_l
    run_type_h         = each.value.run_type_h
    fcst               = each.value.fcst
    member             = each.value.member
    member_suffix      = each.value.member_suffix
    member_path        = each.value.member_path
    nprocs             = each.value.nprocs
    ami_id             = local.cfe_nom_ami_id
    instance_type      = each.value.instance_type
    key_name           = local.cfe_nom_key_name
    security_group_ids = local.cfe_nom_security_groups
    instance_profile   = local.cfe_nom_instance_profile
    volume_size        = each.value.volume_size
  }))}
}
EOT
  }
}

# Analysis/Assimilation CFE_NOM Schedules
resource "aws_scheduler_schedule" "datastream_schedule_AnA_range_cfe_nom" {
  for_each = local.analysis_assim_extend_cfe_nom_config

  name       = "analysis_assim_extend_fcst${each.value.init}_vpu${each.value.vpu}_schedule_cfe_nom_test"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 ${local.analysis_assim_extend_times_cfe_nom[each.key]} * * ? *)"
  schedule_expression_timezone = "America/New_York"

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:sfn:startExecution"
    role_arn = aws_iam_role.scheduler_role.arn
    input    = <<-EOT
{
  "StateMachineArn": "${var.state_machine_arn}",
  "Name": "cfe_nom_analysis_assim_vpu${each.value.vpu}_init${each.value.init}_<aws.scheduler.execution-id>",
  "Input": ${jsonencode(templatefile(local.cfe_nom_template_path, {
    vpu                = each.value.vpu
    init               = each.value.init
    run_type_l         = each.value.run_type_l
    run_type_h         = each.value.run_type_h
    fcst               = each.value.fcst
    member             = each.value.member
    member_suffix      = each.value.member_suffix
    member_path        = each.value.member_path
    nprocs             = each.value.nprocs
    ami_id             = local.cfe_nom_ami_id
    instance_type      = each.value.instance_type
    key_name           = local.cfe_nom_key_name
    security_group_ids = local.cfe_nom_security_groups
    instance_profile   = local.cfe_nom_instance_profile
    volume_size        = each.value.volume_size
  }))}
}
EOT
  }
}
