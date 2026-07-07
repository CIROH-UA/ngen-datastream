# Single-file Terraform root: provisions the controller instance; per-datastream
# YAML + templates are pushed onto it via lxd_instance_file. Collapses the AWS
# modules/orchestration module — one always-on controller replaces five Lambdas
# + Step Functions + EventBridge. Ephemeral workers run under the LXD `default`
# profile (networking) with security.nesting set per-worker at launch (needed
# for the podman-in-LXD container runtime — see lxd.launch_instance).

terraform {
  required_version = ">= 1.5"
  required_providers {
    lxd = {
      source  = "terraform-lxd/lxd"
      version = "~> 2.0"
    }
  }
}

provider "lxd" {
  generate_client_certificates = true
  accept_remote_certificate    = true

  remote {
    name    = var.lxd_remote_name
    address = var.lxd_endpoint
    token   = var.lxd_trust_token
    default = true
  }
}

# Controller instance — the always-on orchestrator that replaces the Lambdas.
locals {
  controller_name = "rds-controller-${var.environment_suffix}"

  # Defaults to the provider's endpoint unless overridden (e.g. host-internal).
  controller_lxd_endpoint = var.controller_lxd_endpoint != "" ? var.controller_lxd_endpoint : var.lxd_endpoint

  controller_user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    package_ref     = var.package_ref
    output_check    = var.output_check
    log_level       = var.log_level
    aws_region      = var.aws_region
    datastreams_dir = "/etc/research-datastream-lxd/datastreams"
    lxd_project     = var.lxd_project

    aws_access_key_id     = var.aws_access_key_id
    aws_secret_access_key = var.aws_secret_access_key

    s3_max_concurrent_requests = var.s3_max_concurrent_requests
    aws_max_attempts           = var.aws_max_attempts
    aws_retry_mode             = var.aws_retry_mode

    core_budget = var.core_budget
    memory_pct  = var.memory_pct
    stagger_s   = var.stagger_s

    controller_lxd_endpoint = local.controller_lxd_endpoint
    lxd_verify              = var.controller_lxd_verify
    client_cert_pem         = file(pathexpand(var.controller_lxd_cert_file))
    client_key_pem          = file(pathexpand(var.controller_lxd_key_file))
  })
}

resource "lxd_instance" "controller" {
  name    = local.controller_name
  project = var.lxd_project
  image   = var.controller_image
  type    = "container"

  profiles = ["default"]

  limits = {
    cpu    = tostring(var.controller_cpu)
    memory = var.controller_memory
  }

  config = {
    "user.user-data"   = local.controller_user_data
    "security.nesting" = "true"
  }

  # Networking (eth0) is inherited from the `default` profile — the same NIC the
  # ephemeral workers get in lxd.launch_instance, which declares no nic device.
  # Keeping both on the default profile guarantees the controller can't land on
  # a different network than the workers it launches.

  # Pin the root disk to the configured pool.
  device {
    name = "root"
    type = "disk"
    properties = {
      path = "/"
      pool = var.lxd_storage_pool
    }
  }
}

# Push per-datastream config files onto the controller, into
# /etc/research-datastream-lxd/datastreams/<name>/... (replaces schedules.tf).
locals {
  datastream_files = {
    for f in fileset("${path.module}/datastreams", "**") :
    f => "${path.module}/datastreams/${f}"
  }
}

resource "lxd_instance_file" "datastream_configs" {
  for_each           = local.datastream_files
  instance           = lxd_instance.controller.name
  project            = var.lxd_project
  source_path        = each.value
  target_path        = "/etc/research-datastream-lxd/datastreams/${each.key}"
  mode               = "0644"
  create_directories = true
}

# Kick the scheduler to pick up config changes after any `apply`.
resource "terraform_data" "reload_scheduler" {
  triggers_replace = {
    datastream_hash = sha256(join("", [for f in sort(keys(local.datastream_files)) : filesha256(local.datastream_files[f])]))
  }
  # Wait for cloud-init to finish (|| true so a degraded boot doesn't fail the
  # apply), then restart so the scheduler reloads the pushed configs. Assumes
  # lxc's default remote is the target host (apply runs on the LXD master).
  provisioner "local-exec" {
    command = <<-EOT
      lxc --project ${var.lxd_project} exec ${lxd_instance.controller.name} -- cloud-init status --wait || true
      lxc --project ${var.lxd_project} exec ${lxd_instance.controller.name} -- systemctl restart research-datastream-lxd
    EOT
  }
  depends_on = [lxd_instance_file.datastream_configs]
}
