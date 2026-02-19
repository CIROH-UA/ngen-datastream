# Security Group for EC2 instances launched by Step Functions

resource "aws_security_group" "datastream_ec2_sg" {
  name_prefix = "${var.resource_prefix}_ec2_sg_"
  description = "Security group for NRDS datastream EC2 instances"
  vpc_id      = data.aws_vpc.default.id

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.resource_prefix}_ec2_sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}
