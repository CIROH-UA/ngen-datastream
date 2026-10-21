# Lambdas that share logic with the LXD orchestrator get research_datastream_core
# (infra/common/python, stdlib only) copied into their zip beside the handler.
locals {
  core_src   = "${path.module}/../../../../common/python/src"
  core_files = fileset(local.core_src, "research_datastream_core/*.py")
}

data "archive_file" "python_lambda_starter" {
  type        = "zip"
  source_file = "${path.module}/lambdas/start_ami/lambda_function.py"
  output_path = "${path.module}/lambdas/starter_lambda.zip"
}

data "archive_file" "python_lambda_commander" {
  type        = "zip"
  output_path = "${path.module}/lambdas/commander_lambda.zip"

  source {
    content  = file("${path.module}/lambdas/streamcommander/lambda_function.py")
    filename = "lambda_function.py"
  }

  dynamic "source" {
    for_each = local.core_files
    content {
      content  = file("${local.core_src}/${source.value}")
      filename = source.value
    }
  }
}

data "archive_file" "python_lambda_poller" {
  type        = "zip"
  source_file = "${path.module}/lambdas/poller/lambda_function.py"
  output_path = "${path.module}/lambdas/poller_lambda.zip"
}

data "archive_file" "python_lambda_checker" {
  type        = "zip"
  output_path = "${path.module}/lambdas/checker_lambda.zip"

  source {
    content  = file("${path.module}/lambdas/checker/lambda_function.py")
    filename = "lambda_function.py"
  }

  dynamic "source" {
    for_each = local.core_files
    content {
      content  = file("${local.core_src}/${source.value}")
      filename = source.value
    }
  }
}

data "archive_file" "python_lambda_stopper" {
  type        = "zip"
  source_file = "${path.module}/lambdas/stopper/lambda_function.py"
  output_path = "${path.module}/lambdas/stopper_lambda.zip"
}

resource "aws_lambda_function" "starter_lambda" {
  function_name    = var.starter_lambda_name
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = "${path.module}/lambdas/starter_lambda.zip"
  source_code_hash = data.archive_file.python_lambda_starter.output_base64sha256
  timeout          = 900
}

resource "aws_lambda_function" "commander_lambda" {
  function_name    = var.commander_lambda_name
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = "${path.module}/lambdas/commander_lambda.zip"
  source_code_hash = data.archive_file.python_lambda_commander.output_base64sha256
  timeout          = 600
}

resource "aws_lambda_function" "poller_lambda" {
  function_name    = var.poller_lambda_name
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = "${path.module}/lambdas/poller_lambda.zip"
  source_code_hash = data.archive_file.python_lambda_poller.output_base64sha256
  timeout          = 900
}

resource "aws_lambda_function" "checker_lambda" {
  function_name    = var.checker_lambda_name
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = "${path.module}/lambdas/checker_lambda.zip"
  source_code_hash = data.archive_file.python_lambda_checker.output_base64sha256
  timeout          = 60
}

resource "aws_lambda_function" "stopper_lambda" {
  function_name    = var.stopper_lambda_name
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = "${path.module}/lambdas/stopper_lambda.zip"
  source_code_hash = data.archive_file.python_lambda_stopper.output_base64sha256
  timeout          = 180
}