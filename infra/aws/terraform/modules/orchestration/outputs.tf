output "datastream_arn" {
  value = aws_sfn_state_machine.datastream_state_machine.arn
}

output "ec2_security_group_id" {
  value       = aws_security_group.datastream_ec2_sg.id
  description = "Security group ID for EC2 instances"
}

resource "local_file" "write_arn" {
  content  = aws_sfn_state_machine.datastream_state_machine.arn
  filename = "${path.module}/sm_ARN.txt"
}
