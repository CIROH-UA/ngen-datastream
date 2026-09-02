
resource "aws_sfn_state_machine" "datastream_state_machine" {
  name     = var.sm_name
  role_arn = aws_iam_role.iam_for_sfn.arn

  # AWS's default 5m delete timeout can be too short if the state machine
  # still has an execution parked in the RetryBackoffWait state (#391) when
  # destroy runs, since Step Functions won't finish tearing the state
  # machine down until in-flight executions have actually stopped.
  timeouts {
    delete = "15m"
  }

  definition = <<EOF
{
  "Comment": "The conductor of the daily ngen datastream",
  "StartAt": "ForcingChecker",
  "States": {
    "ForcingChecker": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "OutputPath": "$.Payload",
      "Parameters": {
        "Payload.$": "$",
        "FunctionName": "${aws_lambda_function.forcing_checker_lambda.arn}:$LATEST"
      },
      "Retry": [
        {
          "ErrorEquals": [
            "Lambda.ServiceException",
            "Lambda.AWSLambdaException",
            "Lambda.SdkClientException",
            "Lambda.TooManyRequestsException",
            "States.Timeout"
          ],
          "IntervalSeconds": 2,
          "MaxAttempts": 6,
          "BackoffRate": 2
        }
      ],
      "Next": "ForcingCheckerChoice"
    },
    "ForcingCheckerChoice": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.ii_forcing_found",
          "BooleanEquals": true,
          "Next": "EC2StarterFromAMI"
        },
        {
          "Variable": "$.ii_forcing_found",
          "BooleanEquals": false,
          "Next": "ForcingCheckerWait"
        }
      ],
      "Default": "ForcingFileNotFound"
    },
    "ForcingCheckerWait": {
      "Type": "Wait",
      "Comment": "Poll interval between forcing-file existence checks. Controlled by forcing_check_wait_s in the event.",
      "SecondsPath": "$.forcing_check_wait_s",
      "Next": "ForcingChecker"
    },
    "ForcingFileNotFound": {
      "Type": "Fail",
      "Error": "ForcingFileNotFound",
      "Cause": "Forcing file was not available within the configured timeout."
    },
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
          "Next": "RetryBackoffWait",
          "And": [
            {
              "Variable": "$.ii_s3_object_checked",
              "BooleanEquals": false
            },
            {
              "Variable": "$.run_options.n_retries_allowed",
              "NumericGreaterThanPath": "$.retry_attempt"
            },
            {
              "Variable": "$.run_options.ii_check_s3",
              "BooleanEquals": true
            }
          ]
        }
      ],
      "Default": "Success, Go to End"
    },
    "RetryBackoffWait": {
      "Type": "Wait",
      "Comment": "Exponential backoff before retrying, giving delayed upstream NWM forcings time to become available (see issue #391)",
      "SecondsPath": "$.wait_seconds",
      "Next": "EC2StarterFromAMI"
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


