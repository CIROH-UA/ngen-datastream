output "datastream_arns" {
  value = aws_sfn_state_machine.datastream_state_machine.arn
}

resource "aws_ssm_parameter" "state_machine_arn" {
  name  = "/datastream/state-machine-arn"
  type  = "String"
  value = aws_sfn_state_machine.datastream_state_machine.arn
}

resource "local_file" "write_arn" {
  content  = aws_sfn_state_machine.datastream_state_machine.arn
  filename = "${path.module}/sm_ARN.txt"
}
