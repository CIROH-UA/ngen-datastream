output "controller_name" {
  value       = lxd_instance.controller.name
  description = "LXD instance name of the always-on orchestrator."
}

output "controller_ipv4" {
  value       = try(lxd_instance.controller.ipv4_address, null)
  description = "Controller's IPv4 address on the LXD network (may be null until network is up)."
}

output "datastream_count" {
  value = length(distinct([for p in keys(local.datastream_files) : split("/", p)[0]]))
}
