output "datastream_arn" {
  value = module.nrds_orchestration.datastream_arn
}

output "ec2_security_group_id" {
  value = module.nrds_orchestration.ec2_security_group_id
}

resource "local_file" "write_arn" {
  content  = module.nrds_orchestration.datastream_arn
  filename = "${path.module}/sm_ARN.txt"
}