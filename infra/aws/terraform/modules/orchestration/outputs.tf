output "datastream_arns" {
  value = aws_sfn_state_machine.datastream_state_machine.arn
}

output "ec2_instance_profile_name" {
  value = aws_iam_instance_profile.instance_profile.name
}

resource "local_file" "write_arn" {
  content  = aws_sfn_state_machine.datastream_state_machine.arn
  filename = "${path.module}/sm_ARN.txt"
}
