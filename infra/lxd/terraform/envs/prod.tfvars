environment_suffix = "prod"

lxd_endpoint     = "https://nextstream.ciroh.ua.edu:443"
lxd_remote_name  = "nextstream"
lxd_project      = "NRDS-Onpremise"
lxd_network      = "nrds_nat"
lxd_storage_pool = "remote"

controller_image  = "ubuntu:22.04"
controller_cpu    = 2
controller_memory = "4GiB"

# Pin the code version with a tag/commit; the controller installs from git.
package_ref = "nrds_lxd"

output_check = "s3"
aws_region   = "us-east-1"

# Controller -> LXD API client cert/key (trust it on the server once). If the
# public endpoint isn't routable from inside the network, set
# controller_lxd_endpoint to the host's internal address.
controller_lxd_cert_file = "~/.config/lxc/client.crt"
controller_lxd_key_file  = "~/.config/lxc/client.key"
# controller_lxd_endpoint = "https://10.x.x.1:8443"

# S3 fan-out tuning + scheduler budgets (size core_budget to the real cluster).
s3_max_concurrent_requests = 4
aws_max_attempts           = 10
aws_retry_mode             = "adaptive"
core_budget                = 256
memory_pct                 = 0.80
stagger_s                  = 10

# Sensitive, set via env vars (do NOT commit):
#   TF_VAR_lxd_trust_token        — one-shot LXD trust token for the provider
#   TF_VAR_aws_access_key_id      — static IAM key forwarded to workers
#   TF_VAR_aws_secret_access_key  — static IAM secret forwarded to workers
