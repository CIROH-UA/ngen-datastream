provider "aws" {
  region = var.region
}

terraform {
  required_version = ">= 0.12"
}

variable "region" {}
variable "starter_lambda_name" {}
variable "commander_lambda_name" {}
variable "poller_lambda_name" {}
variable "checker_lambda_name" {}
variable "stopper_lambda_name" {}
variable "lambda_policy_name" {}
variable "lambda_role_name" {}
variable "lambda_invoke_policy_name" {}
variable "sm_name" {}
variable "sm_role_name" {}
variable "ec2_role" {}
variable "ec2_policy_name" {}
variable "profile_name" {}
variable "scheduler_policy_name" {}
variable "scheduler_role_name" {}
variable "sns_publish_policy_name" {}

resource "aws_iam_role" "ec2_role" {
  name                = var.ec2_role
    assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "ec2.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "ec2_policy" {
  name        = var.ec2_policy_name
  description = "Policy with permissions for datastream EC2"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = [
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel",          
          "ssm:DescribeInstanceInformation",
          "ssm:SendCommand",
          "ssm:GetCommandInvocation",
          "ssm:PutComplianceItems",
          "ssm:UpdateInstanceInformation"
        ],
        Resource = "*"
      },
      {
        Effect   = "Allow",
        Action   = [
          "iam:PassRole"  
        ],
        Resource = "*"
      },
      {
        Effect   = "Allow",
        Action   = [
          "s3:*"  
        ],
        Resource = "*"
      },      
      {
        Effect   = "Allow",
        Action   = [
          "ec2:DescribeInstances",
          "ec2:DescribeTags"
        ],
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ec2_role_custom_policy_attach" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.ec2_policy.arn
}

resource "aws_iam_role_policy_attachment" "ssm_policy_attachment" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "instance_profile" {
  name = var.profile_name
  role = aws_iam_role.ec2_role.name
}

resource "aws_iam_role" "lambda_role" {
  name = var.lambda_role_name
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "datastreamlambda_policy" {
  name        = var.lambda_policy_name
  description = "Policy with permissions for datastreamlambda"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = [
          "ec2:RunInstances",
          "ec2:StartInstances",
          "ec2:StopInstances",
          "ec2:DescribeInstances",
          "ec2:TerminateInstances",
          "ec2:DescribeVolumes",
          "ec2:DeleteVolume",
          "ec2:DetachVolume",
          "ec2:DescribeTags",
          "ec2:CreateTags"
        ],
        Resource = "*"
      },
      {
        Effect   = "Allow",
        Action   = [
          "ssm:SendCommand",
          "ssm:GetCommandInvocation",
          "ssm:DescribeInstanceInformation"
        ],
        Resource = "*"
      },
      {
        Effect   = "Allow",
        Action   = [
          "iam:PassRole"  
        ],
        Resource = "*"
      },
      {
        Effect   = "Allow",
        Action   = [
          "s3:*"  
        ],
        Resource = "*"
      },      
      {
      "Effect": "Deny",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }    
    ]
  })
}

resource "aws_iam_policy_attachment" "datastream_attachment" {
  name       = "datastream_attachment"
  roles      = [aws_iam_role.lambda_role.name]
  policy_arn = aws_iam_policy.datastreamlambda_policy.arn
}

resource "aws_iam_role_policy_attachment" "ssm_policy_attachment2" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "archive_file" "python_lambda_starter" {  
  type = "zip"  
  source_file = "${path.module}/lambda_functions/start_ami/lambda_function.py" 
  output_path = "${path.module}/lambda_functions/starter_lambda.zip"
}

data "archive_file" "python_lambda_commander" {  
  type = "zip"  
  source_file = "${path.module}/lambda_functions/streamcommander/lambda_function.py" 
  output_path = "${path.module}/lambda_functions/commander_lambda.zip"
}

data "archive_file" "python_lambda_poller" {  
  type = "zip"  
  source_file = "${path.module}/lambda_functions/poller/lambda_function.py" 
  output_path = "${path.module}/lambda_functions/poller_lambda.zip"
}

data "archive_file" "python_lambda_checker" {  
  type = "zip"  
  source_file = "${path.module}/lambda_functions/checker/lambda_function.py" 
  output_path = "${path.module}/lambda_functions/checker_lambda.zip"
}

data "archive_file" "python_lambda_stopper" {  
  type = "zip"  
  source_file = "${path.module}/lambda_functions/stopper/lambda_function.py" 
  output_path = "${path.module}/lambda_functions/stopper_lambda.zip"
}

resource "aws_lambda_function" "starter_lambda" {
  function_name = var.starter_lambda_name
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  filename      = "${path.module}/lambda_functions/starter_lambda.zip"
  timeout       = 360
}

resource "aws_lambda_function" "commander_lambda" {
  function_name = var.commander_lambda_name
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  filename      = "${path.module}/lambda_functions/commander_lambda.zip"
  timeout       = 600
}

resource "aws_lambda_function" "poller_lambda" {
  function_name = var.poller_lambda_name
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  filename      = "${path.module}/lambda_functions/poller_lambda.zip"
  timeout       = 900
}

resource "aws_lambda_function" "checker_lambda" {
  function_name = var.checker_lambda_name
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  filename      = "${path.module}/lambda_functions/checker_lambda.zip"
  timeout       = 60
}

resource "aws_lambda_function" "stopper_lambda" {
  function_name = var.stopper_lambda_name
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  filename      = "${path.module}/lambda_functions/stopper_lambda.zip"
  timeout       = 180
}


resource "aws_iam_role" "iam_for_sfn" {
  name = var.sm_role_name
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "states.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "lambda_invoke_policy" {
  name        = var.lambda_invoke_policy_name
  description = "Policy to allow invoking Lambda functions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow",
      Action    = "lambda:InvokeFunction",
      Resource  = [ "*"
        ]
    }]
  })
}

resource "aws_iam_policy" "sns_publish_policy" {
  name        = var.sns_publish_policy_name
  description = "Policy to allow invoking Lambda functions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow",
      Action   = "sns:Publish",
      Resource = "arn:aws:sns:us-east-1:879381264451:AlertJordanOnDataStreamFailure"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_invoke_attachment" {
  role       = aws_iam_role.iam_for_sfn.name
  policy_arn = aws_iam_policy.lambda_invoke_policy.arn
}

resource "aws_iam_role_policy_attachment" "sns_publish_attachment" {
  role       = aws_iam_role.iam_for_sfn.name
  policy_arn = aws_iam_policy.sns_publish_policy.arn
}

resource "aws_sfn_state_machine" "datastream_state_machine" {
  name       = var.sm_name
  role_arn   = aws_iam_role.iam_for_sfn.arn
  definition = <<EOF
{
  "Comment": "The conductor of the daily ngen datastream",
  "StartAt": "EC2StarterFromAMI",
  "States": {
    "EC2StarterFromAMI": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "OutputPath": "$.Payload",
      "Parameters": {
        "Payload.$": "$",
        "FunctionName": "${aws_lambda_function.starter_lambda.arn}:$LATEST"
      },      
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException",
          "Lambda.AWSLambdaException", 
          "Lambda.SdkClientException", 
          "Lambda.TooManyRequestsException", 
          "States.Timeout"
          ],
          "IntervalSeconds": 2,
          "MaxAttempts": 10,
          "BackoffRate": 2
        }
      ],
      "Next": "Commander",
      "Catch": [
        {
          "ErrorEquals": [
            "States.ALL"
          ],
          "Comment": "",
          "Next": "EC2Stopper",
          "ResultPath": "$.failedInput"
        }
      ]
    },
    "Commander": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "OutputPath": "$.Payload",
      "Parameters": {
        "Payload.$": "$",
        "FunctionName": "${aws_lambda_function.commander_lambda.arn}:$LATEST"
      },      
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException",
          "Lambda.AWSLambdaException", 
          "Lambda.SdkClientException", 
          "Lambda.TooManyRequestsException", 
          "States.Timeout"
          ],
          "IntervalSeconds": 2,
          "MaxAttempts": 10,
          "BackoffRate": 2
        }
      ],
      "Next": "EC2Poller",
      "Catch": [
        {
          "ErrorEquals": [
            "States.ALL"
          ],
          "Comment": "",
          "Next": "EC2Stopper",
          "ResultPath": "$.failedInput"
        }
      ]
    },
    "EC2Poller": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "OutputPath": "$.Payload",
      "Parameters": {
        "Payload.$": "$",
        "FunctionName": "${aws_lambda_function.poller_lambda.arn}:$LATEST"
      }, 
      "Next": "Choice",
      "Retry": [
        {
          "ErrorEquals": ["States.Timeout"],
          "IntervalSeconds": 1,
          "MaxAttempts": 100,
          "BackoffRate": 1,
          "Comment": "Retry for a long time just in case datastream takes awhile"
        }
      ],
      "Catch": [
        {
          "ErrorEquals": [
            "States.ALL"
          ],
          "Comment": "",
          "Next": "EC2Stopper",
          "ResultPath": "$.failedInput"
        }
      ]
    },
    "Choice": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.ii_pass",
          "BooleanEquals": true,
          "Next": "RunChecker"
        },
        {
          "Variable": "$.ii_pass",
          "BooleanEquals": false,
          "Next": "EC2Poller"
        }
      ]
    },
    "RunChecker": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "OutputPath": "$.Payload",
      "Parameters": {
        "Payload.$": "$",
        "FunctionName": "${aws_lambda_function.checker_lambda.arn}:$LATEST"
      },
      "Next": "EC2Stopper",
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException", "Lambda.TooManyRequestsException"],
          "IntervalSeconds": 1,
          "MaxAttempts": 3,
          "BackoffRate": 2
        }
      ],
      "Catch": [
        {
          "ErrorEquals": [
            "States.ALL"
          ],
          "Comment": "",
          "Next": "EC2Stopper",
          "ResultPath": "$.failedInput"
        }
      ]
    },
    "Retry Choice": {
      "Type": "Choice",
      "Choices": [
        {
          "Next": "EC2StarterFromAMI",
          "And": [
            {
              "Variable": "$.ii_s3_object_checked",
              "BooleanEquals": false
            },
            {
              "Variable": "$.run_options.n_retries_allowed",
              "NumericGreaterThanPath": "$.retry_attempt"
            }
          ]
        },
        {
          "Next": "AlertJordan",
          "And": [
            {
              "Variable": "$.ii_s3_object_checked",
              "BooleanEquals": false
            },
            {
              "Variable": "$.run_options.n_retries_allowed",
              "NumericEqualsPath": "$.retry_attempt"
            }
          ]
        }
      ],
      "Default": "Success, Go to End"
    },
    "Success, Go to End": {
      "Type": "Pass",
      "End": true
    },
    "AlertJordan": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "Message.$": "$",
        "TopicArn": "arn:aws:sns:us-east-1:879381264451:AlertJordanOnDataStreamFailure"
      },
      "End": true,
      "ResultPath": "$.failedInput"
    },
    "EC2Stopper": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "OutputPath": "$.Payload",
      "Parameters": {
        "Payload.$": "$",
        "FunctionName": "${aws_lambda_function.stopper_lambda.arn}:$LATEST"
      },
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException", "Lambda.TooManyRequestsException"],
          "IntervalSeconds": 1,
          "MaxAttempts": 3,
          "BackoffRate": 2
        }
      ],
      "Next": "Retry Choice",
      "Catch": [
        {
          "ErrorEquals": [
            "States.ALL"
          ],
          "Next": "AlertJordan"
        }
      ]
    }
  }
}
EOF
}

resource "local_file" "write_arn" {
  content  = aws_sfn_state_machine.datastream_state_machine.arn
  filename = "${path.module}/sm_ARN.txt"
}

output "datastream_arns" {
  value = aws_sfn_state_machine.datastream_state_machine.arn
}

resource "aws_iam_policy" "scheduler_policy" {
  name        = var.scheduler_policy_name
  description = "Policy with permissions for statemachine execution"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
            "Effect": "Allow",
            Action = [
                "states:StartExecution",
                "events:PutTargets",
                "events:PutRule",
                "events:PutPermission"
              ],
            "Resource": ["*"]
        }
    ]
  })
}

resource "aws_iam_role" "scheduler_role" {
  name = var.scheduler_role_name
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "scheduler.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy_attachment" "datastream_scheduler_attachment" {
  name       = "datastream_scheduler_attachment"
  roles      = [aws_iam_role.scheduler_role.name]
  policy_arn = aws_iam_policy.scheduler_policy.arn
}



locals {
  init_cycles_config = jsondecode(file("${path.module}/executions/execution_forecast_inputs.json"))

  # 01, 07, and 17 removed for now
  # vpus = [
  #   "fp","02","03N","03S","03W","04",
  #   "05","06","08","09","10L",
  #   "10U","11","12","13","14","15",
  #   "16","18"
  # ]
  vpus = [
    "fp","16"
  ]  
  short_range_paths = {
    for pair in flatten([
      for init in local.init_cycles_config.short_range.init_cycles : [
        for vpu in local.vpus : {
          key   = "${init}_${vpu}"
          value = "${path.module}/executions/short_range/${init}/execution_datastream_${vpu}.json"
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
          value = "${path.module}/executions/analysis_assim_extend/${init}/execution_datastream_${vpu}.json"
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

  # medium_vpus = [
  #   "fp","02","03N","03S","03W","04","06","08","09","12","13","14","15","16","18"
  # ] 
  medium_vpus = [
    "fp","16"
  ]    

  medium_range_paths = {
    for pair in flatten([
      for init in local.init_cycles_config.medium_range.init_cycles : [
        for member in local.init_cycles_config.medium_range.ensemble_members : [
          for vpu in local.medium_vpus : {
            key   = "${init}_${member}_${vpu}"
            value = "${path.module}/executions/medium_range/${init}/${member}/execution_datastream_${vpu}.json"
          }
        ]
      ]
    ]) : pair.key => pair.value
  }
  medium_range_times = {
    for pair in flatten([
      for init in local.init_cycles_config.medium_range.init_cycles : [
        for member in local.init_cycles_config.medium_range.ensemble_members : [
          for vpu in local.medium_vpus : {
            key   = "${init}_${member}_${vpu}"
            value = "${vpu}" == "fp"? (tonumber("${init}")+4) % 24 : (tonumber("${init}") + 5) % 24
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

  schedule_expression        = "cron(15 ${local.medium_range_times[each.key]} * * ? *)"
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