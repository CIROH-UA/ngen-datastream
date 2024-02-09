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
variable "sm_name" {}
variable "runtime" {}
variable "schedule_name" {}
variable "scheduler_policy_name" {}
variable "scheduler_role_name" {}
variable "execution_name" {}

resource "aws_iam_policy" "datastreamlambda_policy" {
  name        = var.lambda_policy_name
  description = "Policy with permissions for datastreamlambda"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "iam:GetRole",
          "iam:PassRole"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "arn:aws:logs:*:*:*"
      },      
      {
        Effect = "Allow",
        Action = [
          "ssm:SendCommand",
          "ssm:DescribeInstanceInformation",
          "ssm:GetCommandInvocation",
          "ssm:GetDeployablePatchSnapshotForInstance",
          "ssm:GetDocument",
          "ssm:DescribeDocument",
          "ssm:GetManifest",
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:ListAssociations",
          "ssm:ListInstanceAssociations",
          "ssm:PutInventory",
          "ssm:PutComplianceItems",
          "ssm:PutConfigurePackageResult",
          "ssm:UpdateAssociationStatus",
          "ssm:UpdateInstanceAssociationStatus",
          "ssm:UpdateInstanceInformation"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "s3:*"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "ec2messages:AcknowledgeMessage",
          "ec2messages:DeleteMessage",
          "ec2messages:FailMessage",
          "ec2messages:GetEndpoint",
          "ec2messages:GetMessages",
          "ec2messages:SendReply"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel"
        ],
        Resource = "*"
      },
       {
        Effect   = "Allow"
        Action   = [
          "ec2:*"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role" "datastreamlambda_role" {
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

resource "aws_iam_policy_attachment" "datastream_attachment" {
  name       = "datastream_attachment"
  roles      = [aws_iam_role.datastreamlambda_role.name]
  policy_arn = aws_iam_policy.datastreamlambda_policy.arn
}


resource "aws_lambda_function" "starter_lambda" {
  function_name = var.starter_lambda_name
  role          = aws_iam_role.datastreamlambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = var.runtime
  filename      = "${path.module}/lambda_functions/starter_lambda.zip"
  timeout       = 180
}

resource "aws_lambda_function" "commander_lambda" {
  function_name = var.commander_lambda_name
  role          = aws_iam_role.datastreamlambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = var.runtime
  filename      = "${path.module}/lambda_functions/commander_lambda.zip"
  timeout       = 60
}

resource "aws_lambda_function" "poller_lambda" {
  function_name = var.poller_lambda_name
  role          = aws_iam_role.datastreamlambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = var.runtime
  filename      = "${path.module}/lambda_functions/poller_lambda.zip"
  timeout       = 900
}

resource "aws_lambda_function" "checker_lambda" {
  function_name = var.checker_lambda_name
  role          = aws_iam_role.datastreamlambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = var.runtime
  filename      = "${path.module}/lambda_functions/checker_lambda.zip"
  timeout       = 60
}

resource "aws_lambda_function" "stopper_lambda" {
  function_name = var.stopper_lambda_name
  role          = aws_iam_role.datastreamlambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = var.runtime
  filename      = "${path.module}/lambda_functions/stopper_lambda.zip"
  timeout       = 180
}


resource "aws_iam_role" "iam_for_sfn" {
  name = "statemachine_role"
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
  name        = "lambda_invoke_policy"
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

resource "aws_scheduler_schedule" "data_stream_schedule" {
  name       = var.schedule_name
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = "cron(0 1 * * ? *)"  
  schedule_expression_timezone  = "America/New_York"

  target {
    arn      = aws_sfn_state_machine.datastream_state_machine.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input = file("${path.module}/${var.execution_name}")
  }

}