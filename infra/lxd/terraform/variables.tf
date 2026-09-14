variable "lxd_endpoint" {
  type        = string
  description = "HTTPS endpoint of the LXD server, e.g. https://lxd.example.edu:8443"
}

variable "lxd_trust_token" {
  type        = string
  description = "One-shot trust token produced by `lxc config trust add --name <you>`."
  sensitive   = true
}

variable "lxd_remote_name" {
  type    = string
  default = "nextstream"
}

variable "lxd_project" {
  type    = string
  default = "default"
}

variable "lxd_storage_pool" {
  type    = string
  default = "default"
}

variable "environment_suffix" {
  type        = string
  description = "Appended to instance and profile names, e.g. prod, dev."
}

# ---- controller --------------------------------------------------------

variable "controller_image" {
  type        = string
  default     = "ubuntu:22.04"
  description = "LXD image alias for the always-on controller."
}

variable "controller_cpu" {
  type    = number
  default = 2
}

variable "controller_memory" {
  type    = string
  default = "4GiB"
}

variable "package_ref" {
  type        = string
  default     = "main"
  description = "Git ref (tag/branch/commit) of this repo the controller pip-installs the orchestrator + shared core package from."
}

# ---- orchestrator runtime options --------------------------------------

variable "output_check" {
  type        = string
  default     = "none"
  description = "Backend for verifying run outputs. One of: none, s3."
  validation {
    condition     = contains(["none", "s3"], var.output_check)
    error_message = "output_check must be 'none' or 's3'."
  }
}

variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "Only used when output_check = 's3'."
}

# ---- AWS credentials ----------------------------------------------------
# Static IAM keys written to the controller's env and forwarded into workers'
# `aws s3` calls. Use a long-lived IAM user, NOT STS/SSO creds: no
# AWS_SESSION_TOKEN is forwarded, so a session token would break worker uploads.

variable "aws_access_key_id" {
  type        = string
  default     = ""
  sensitive   = true
  description = "AWS access key id forwarded to the controller + workers. Set via TF_VAR_aws_access_key_id."
}

variable "aws_secret_access_key" {
  type        = string
  default     = ""
  sensitive   = true
  description = "AWS secret access key forwarded to the controller + workers. Set via TF_VAR_aws_secret_access_key."
}

# ---- controller -> LXD API connection -----------------------------------
# The controller is an LXD instance, so it reaches the API over HTTPS with a
# client cert/key (trust it on the server once: `lxc config trust add
# client.crt`) rather than the host unix socket. cloud-init places these files.

variable "controller_lxd_endpoint" {
  type        = string
  default     = ""
  description = "HTTPS LXD endpoint the controller uses to reach the API from inside the LXD network. Defaults to var.lxd_endpoint; override if the public name isn't routable from there."
}

variable "controller_lxd_cert_file" {
  type        = string
  default     = "~/.config/lxc/client.crt"
  description = "Path to a PEM client certificate already trusted on the LXD server. Read at apply time and written onto the controller."
}

variable "controller_lxd_key_file" {
  type        = string
  default     = "~/.config/lxc/client.key"
  description = "Path to the PEM private key for controller_lxd_cert_file. Read at apply time and written onto the controller."
}

variable "controller_lxd_verify" {
  type        = string
  default     = "false"
  description = "LXD_VERIFY on the controller: false (skip), true (system CA), or a cert path to pin."
}

# ---- S3 connection-pressure tuning --------------------------------------

variable "s3_max_concurrent_requests" {
  type        = number
  default     = 4
  description = "Per-container `aws s3` max_concurrent_requests cap. Bounds total egress connections (= concurrent workers x this) so fan-out doesn't exhaust the shared NAT/DNS."
}

variable "aws_max_attempts" {
  type    = number
  default = 10
}

variable "aws_retry_mode" {
  type    = string
  default = "adaptive"
}

# ---- scheduler concurrency budgets --------------------------------------

variable "core_budget" {
  type        = number
  default     = 256
  description = "Cluster-wide cpu cores the scheduler may hand out at once (RDS_LXD_CORE_BUDGET). Size to the real cluster."
}

variable "memory_pct" {
  type        = number
  default     = 0.80
  description = "Per-node RAM ceiling fraction for run placement (RDS_LXD_MEMORY_PCT). 0 disables the memory guard."
}

variable "stagger_s" {
  type        = number
  default     = 10
  description = "Seconds between consecutive worker launches (RDS_LXD_STAGGER_S)."
}

variable "log_level" {
  type    = string
  default = "INFO"
}
