output "datastream_arns" {
  value = module.nrds_orchestration.datastream_arns
}

resource "local_file" "write_arn" {
  content  = module.nrds_orchestration.datastream_arns
  filename = "${path.module}/sm_ARN.txt"
}
