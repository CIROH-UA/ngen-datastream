# IAM Role and Policy for AWS Scheduler to start Step Functions executions

resource "aws_iam_policy" "scheduler_policy" {
  name        = var.scheduler_policy_name
  description = "Policy with permissions for statemachine execution"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        "Effect" : "Allow",
        Action = [
          "states:StartExecution",
          "events:PutTargets",
          "events:PutRule",
          "events:PutPermission"
        ],
        "Resource" : ["*"]
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

resource "aws_iam_role_policy_attachment" "datastream_scheduler_attachment" {
  role       = aws_iam_role.scheduler_role.name
  policy_arn = aws_iam_policy.scheduler_policy.arn
}
