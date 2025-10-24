# Terraform configuration for AWS Scheduler to trigger Step Functions executions for NRDS LSTM

locals {
  init_cycles_config = jsondecode(file("${path.module}/executions/execution_forecast_inputs_lstm.json"))

  vpus = [
    "fp","01","02","03N","03S","03W","04",
    "05","06","07","08","09","10L",
    "10U","11","12","13","14","15",
    "16","17","18"
  ]

  short_range_paths = {
    for pair in flatten([
      for init in local.init_cycles_config.short_range.init_cycles : [
        for vpu in local.vpus : {
          key   = "${init}_${vpu}"
          value = "${path.module}/executions/lstm/short_range/${init}/execution_datastream_${vpu}.json"
        }
      ]
    ]) : pair.key => pair.value
  }

  short_range_times = {
    for pair in flatten([
      for init in local.init_cycles_config.short_range.init_cycles : [
        for vpu in local.vpus : {
          key   = "${init}_${vpu}"
          value = "${vpu}" == "fp"? (tonumber("${init}")) % 24 : (tonumber("${init}") + 1) % 24
        }
      ]
    ]) : pair.key => pair.value
  }

  analysis_assim_extend_paths = {
    for pair in flatten([
      for init in local.init_cycles_config.analysis_assim_extend.init_cycles : [
        for vpu in local.vpus : {
          key   = "${init}_${vpu}"
          value = "${path.module}/executions/lstm/analysis_assim_extend/${init}/execution_datastream_${vpu}.json"
        }
      ]
    ]) : pair.key => pair.value
  }

  analysis_assim_extend_times = {
    for pair in flatten([
      for init in local.init_cycles_config.analysis_assim_extend.init_cycles : [
        for vpu in local.vpus : {
          key   = "${init}_${vpu}"
          value = "${vpu}" == "fp"? 15 : 16
        }
      ]
    ]) : pair.key => pair.value
  }

  medium_range_paths = {
    for pair in flatten([
      for init in local.init_cycles_config.medium_range.init_cycles : [
        for vpu in local.vpus : [
          for member in (
            vpu == "fp" ? [1] : local.init_cycles_config.medium_range.ensemble_members
          ) : {
            key   = "${init}_${member}_${vpu}"
            value = "${path.module}/executions/lstm/medium_range/${init}/${member}/execution_datastream_${vpu}.json"
          }
        ]
      ]
    ]) : pair.key => pair.value
  }

  medium_range_times = {
    for pair in flatten([
      for init in local.init_cycles_config.medium_range.init_cycles : [
        for vpu in local.vpus : [
          for member in (
            vpu == "fp" ? [1] : local.init_cycles_config.medium_range.ensemble_members
          ) : {
            key   = "${init}_${member}_${vpu}"
            value = vpu == "fp" ? (tonumber(init) + 2) % 24 : (tonumber(init) + 3) % 24
          }
        ]
      ]
    ]) : pair.key => pair.value
  }


  medium_range_member_offsets = {
    for pair in flatten([
      for init in local.init_cycles_config.medium_range.init_cycles : [
        for member in local.init_cycles_config.medium_range.ensemble_members : [
          for vpu in local.vpus : {
            key   = "${init}_${member}_${vpu}"
            value = ((tonumber("${member}") - 1) * (1/7) * 60) % 60
          }
        ]
      ]
    ]) : pair.key => pair.value
  }
}

resource "aws_scheduler_schedule" "datastream_schedule_short_range" {
  for_each = {
    for forecast, paths in local.short_range_paths :
    forecast => paths
  }

  name       = "short_range_fcst${split("_", each.key)[0]}_vpu${split("_", each.key)[1]}_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression        = "cron(0 ${local.short_range_times[each.key]} * * ? *)"
  schedule_expression_timezone = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file(each.value)
  }
}

resource "aws_scheduler_schedule" "datastream_schedule_medium_range" {
  for_each = {
    for forecast, paths in local.medium_range_paths :
    forecast => paths
  }

  name       = "medium_range_fcst${split("_", each.key)[0]}_mem${split("_", each.key)[1]}_vpu${split("_", each.key)[2]}_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression        = "cron(${local.medium_range_member_offsets[each.key]} ${local.medium_range_times[each.key]} * * ? *)"
  schedule_expression_timezone = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file(each.value)
  }
}

resource "aws_scheduler_schedule" "datastream_schedule_AnA_range" {
  for_each = {
    for forecast, paths in local.analysis_assim_extend_paths :
    forecast => paths
  }

  name       = "analysis_assim_extend_fcst${split("_", each.key)[0]}_vpu${split("_", each.key)[1]}_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression        = "cron(0 ${local.analysis_assim_extend_times[each.key]} * * ? *)"
  schedule_expression_timezone = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file(each.value)
  }
}
