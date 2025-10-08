# IAM Role and Policy for EC2 Instances

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