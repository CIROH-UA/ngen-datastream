
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
        }
      ],
      "Default": "Success, Go to End"
    },
    "Success, Go to End": {
      "Type": "Pass",
      "End": true
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
      "Next": "Retry Choice"
    }
  }
}
EOF
}


