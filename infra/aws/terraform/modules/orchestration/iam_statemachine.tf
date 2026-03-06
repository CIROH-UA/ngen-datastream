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
      Effect = "Allow",
      Action = "lambda:InvokeFunction",
      Resource = [
        "${aws_lambda_function.starter_lambda.arn}:*",
        aws_lambda_function.starter_lambda.arn,
        "${aws_lambda_function.commander_lambda.arn}:*",
        aws_lambda_function.commander_lambda.arn,
        "${aws_lambda_function.poller_lambda.arn}:*",
        aws_lambda_function.poller_lambda.arn,
        "${aws_lambda_function.checker_lambda.arn}:*",
        aws_lambda_function.checker_lambda.arn,
        "${aws_lambda_function.stopper_lambda.arn}:*",
        aws_lambda_function.stopper_lambda.arn,
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_invoke_attachment" {
  role       = aws_iam_role.iam_for_sfn.name
  policy_arn = aws_iam_policy.lambda_invoke_policy.arn
}