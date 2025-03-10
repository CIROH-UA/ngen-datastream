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
  timeout       = 180
}

resource "aws_lambda_function" "commander_lambda" {
  function_name = var.commander_lambda_name
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  filename      = "${path.module}/lambda_functions/commander_lambda.zip"
  timeout       = 60
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

resource "aws_iam_role_policy_attachment" "lambda_invoke_attachment" {
  role       = aws_iam_role.iam_for_sfn.name
  policy_arn = aws_iam_policy.lambda_invoke_policy.arn
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
          "ErrorEquals": ["States.TaskFailed"],
          "Next": "EC2Stopper",
          "Comment": "Kill EC2 in case of failure",
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
          "ErrorEquals": ["States.TaskFailed"],
          "Next": "EC2Stopper",
          "Comment": "Kill EC2 in case of failure",
          "ResultPath": "$.failedInput"
        }
      ]
    },
    "EC2Poller": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "OutputPath": "$.Payload",
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
          "ErrorEquals": ["States.TaskFailed"],
          "Next": "EC2Stopper",
          "Comment": "Kill EC2 in case of failure",
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
          "ErrorEquals": ["States.TaskFailed"],
          "Next": "EC2Stopper",
          "Comment": "Kill EC2 in case of failure",
          "ResultPath": "$.failedInput"
        }
      ]
    },
    "EC2Stopper": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "OutputPath": "$.Payload",
      "Parameters": {
        "Payload.$": "$",
        "FunctionName": "${aws_lambda_function.stopper_lambda.arn}:$LATEST"
      },
      "End": true,
      "Retry": [
        {
          "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException", "Lambda.TooManyRequestsException"],
          "IntervalSeconds": 1,
          "MaxAttempts": 3,
          "BackoffRate": 2
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


# SHORT RANGE SCHEDULES
resource "aws_scheduler_schedule" "datastream_schedule_short_range_fp" {
  name       = "fp_short_range_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "cron(0 3 * * ? *)"  
  schedule_expression_timezone  = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file("${path.module}/executions/short_range/execution_datastream_fp.json")
  }
}
# resource "aws_scheduler_schedule" "datastream_schedule_short_range_01" {
#   name       = "01_short_range_schedule"
#   group_name = "default"

#   flexible_time_window {
#     mode = "OFF"
#   }

#   schedule_expression = "cron(0 4 * * ? *)"  
#   schedule_expression_timezone  = "America/New_York"

#   target {
#     arn      = aws_sfn_state_machine.datastream_state_machine.arn
#     role_arn = aws_iam_role.scheduler_role.arn
#     input    = file("${path.module}/executions/short_range/execution_datastream_01.json")
#   }
# }
resource "aws_scheduler_schedule" "datastream_schedule_short_range_02" {
  name       = "02_short_range_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "cron(0 4 * * ? *)"  
  schedule_expression_timezone  = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file("${path.module}/executions/short_range/execution_datastream_02.json")
  }
}
resource "aws_scheduler_schedule" "datastream_schedule_short_range_03W" {
  name       = "03W_short_range_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "cron(0 4 * * ? *)"  
  schedule_expression_timezone  = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file("${path.module}/executions/short_range/execution_datastream_03W.json")
  }
}
resource "aws_scheduler_schedule" "datastream_schedule_short_range_16" {
  name       = "16_short_range_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "cron(0 4 * * ? *)"  
  schedule_expression_timezone  = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file("${path.module}/executions/short_range/execution_datastream_16.json")
  }
}

# MEDIUM RANGE SCHEDULES
resource "aws_scheduler_schedule" "datastream_schedule_medium_range" {
  name       = "fp_medium_range_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "cron(0 3 * * ? *)"  
  schedule_expression_timezone  = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file("${path.module}/executions/medium_range/execution_datastream_fp.json")
  }

}
# resource "aws_scheduler_schedule" "datastream_schedule_medium_range_01" {
#   name       = "01_medium_range_schedule"
#   group_name = "default"

#   flexible_time_window {
#     mode = "OFF"
#   }

#   schedule_expression = "cron(0 4 * * ? *)"  
#   schedule_expression_timezone  = "America/New_York"

#   target {
#     arn      = aws_sfn_state_machine.datastream_state_machine.arn
#     role_arn = aws_iam_role.scheduler_role.arn
#     input    = file("${path.module}/executions/medium_range/execution_datastream_01.json")
#   }
# }

resource "aws_scheduler_schedule" "datastream_schedule_medium_range_02" {
  name       = "02_medium_range_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "cron(0 4 * * ? *)"  
  schedule_expression_timezone  = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file("${path.module}/executions/medium_range/execution_datastream_02.json")
  }
}
resource "aws_scheduler_schedule" "datastream_schedule_medium_range_03W" {
  name       = "03W_medium_range_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "cron(0 4 * * ? *)"  
  schedule_expression_timezone  = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file("${path.module}/executions/medium_range/execution_datastream_03W.json")
  }
}
resource "aws_scheduler_schedule" "datastream_schedule_medium_range_16" {
  name       = "16_medium_range_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "cron(0 4 * * ? *)"  
  schedule_expression_timezone  = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file("${path.module}/executions/medium_range/execution_datastream_16.json")
  }
}


# ANALYSIS_ASSIM_EXTEND SCHEDULES
resource "aws_scheduler_schedule" "datastream_schedule_analysis_assim_extend" {
  name       = "fp_analysis_assim_extend_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "cron(0 16 * * ? *)"  
  schedule_expression_timezone  = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file("${path.module}/executions/analysis_assim_extend/execution_datastream_fp.json")
  }
}

# resource "aws_scheduler_schedule" "datastream_schedule_analysis_assim_extend_01" {
#   name       = "01_analysis_assim_extend_schedule"
#   group_name = "default"

#   flexible_time_window {
#     mode = "OFF"
#   }

#   schedule_expression = "cron(0 17 * * ? *)"  
#   schedule_expression_timezone  = "America/New_York"

#   target {
#     arn      = aws_sfn_state_machine.datastream_state_machine.arn
#     role_arn = aws_iam_role.scheduler_role.arn
#     input    = file("${path.module}/executions/analysis_assim_extend/execution_datastream_01.json")
#   }
# }

resource "aws_scheduler_schedule" "datastream_schedule_analysis_assim_extend_02" {
  name       = "02_analysis_assim_extend_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "cron(0 17 * * ? *)"  
  schedule_expression_timezone  = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file("${path.module}/executions/analysis_assim_extend/execution_datastream_02.json")
  }
}
resource "aws_scheduler_schedule" "datastream_schedule_analysis_assim_extend_03W" {
  name       = "03W_analysis_assim_extend_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "cron(0 17 * * ? *)"  
  schedule_expression_timezone  = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file("${path.module}/executions/analysis_assim_extend/execution_datastream_03W.json")
  }
}
resource "aws_scheduler_schedule" "datastream_schedule_analysis_assim_extend_16" {
  name       = "16_analysis_assim_extend_schedule"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "cron(0 17 * * ? *)"  
  schedule_expression_timezone  = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = file("${path.module}/executions/analysis_assim_extend/execution_datastream_16.json")
  }
}

# variable "execution_names" {
#   type    = list(string)
#   default = ["01","02","03W","16"]
# }

# resource "aws_scheduler_schedule" "datastream_schedule_short_range" {
#   for_each   = toset(var.vpu_execution_names)
#   name       = "short_range_${each.value}"
#   group_name = "default"

#   flexible_time_window {
#     mode = "OFF"
#   }

#   schedule_expression = "cron(0 1 * * ? *)"  
#   schedule_expression_timezone  = "America/New_York"

#   target {
#     arn      = aws_sfn_state_machine.datastream_state_machine.arn
#     role_arn = aws_iam_role.scheduler_role.arn
#     input = file("${path.module}/executions/short_range/${var.execution_name}_${each.value}.json")
#   }

# }

# resource "aws_scheduler_schedule" "datastream_schedule_medium_range" {
#   for_each   = toset(var.vpu_execution_names)
#   name       = "medium_range_${each.value}"
#   group_name = "default"

#   flexible_time_window {
#     mode = "OFF"
#   }

#   schedule_expression = "cron(0 1 * * ? *)"  
#   schedule_expression_timezone  = "America/New_York"

#   target {
#     arn      = aws_sfn_state_machine.datastream_state_machine.arn
#     role_arn = aws_iam_role.scheduler_role.arn
#     input = file("${path.module}/executions/medium_range/${var.execution_name}_${each.value}.json")
#   }

# }