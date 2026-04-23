# Docker Daemon Warm-up Optimization

**Date:** 2026-03-31
**Status:** Approved

## Problem

When an EC2 instance boots from the NRDS AMI and receives its first `docker run` command via SSM, the Docker daemon takes ~1 minute to become responsive. This penalty hits every execution across all datastreams — with ~1,200+ daily EC2 instances, that is ~20 hours of wasted compute per day.

## Root Cause

The AMI build (`shell/create_ami.sh`) installs Docker, enables it via systemd, and pulls images. However:
1. The daemon config is left at defaults, causing runtime detection of storage driver, log driver, etc. on every boot.
2. Docker's internal overlay metadata may not be fully materialized on disk before the AMI snapshot, requiring reconstruction on first boot.
3. No health check exists in execution templates, so a slow daemon start manifests as an opaque delay on the first `docker run`.

## Solution

Two changes: optimize Docker configuration in the AMI build, and add a health check to execution templates.

### Part 1: AMI Build Changes (`shell/create_ami.sh`)

**1a. Write `/etc/docker/daemon.json` after Docker install, before image pulls:**

```json
{
  "storage-driver": "overlay2",
  "log-driver": "local",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "live-restore": true,
  "default-ulimits": {
    "nofile": { "Name": "nofile", "Hard": 65536, "Soft": 65536 }
  }
}
```

Rationale:
- `storage-driver: overlay2` — explicit declaration avoids runtime probe (overlay2 is already the default on AL2023, but making it explicit skips the detection logic).
- `log-driver: local` — faster than the default `journald` driver; avoids systemd journal overhead on every container log write.
- `live-restore: true` — enables faster daemon restarts by keeping containers running during daemon restart.
- `default-ulimits` — pre-sets file descriptor limits to avoid per-container negotiation.

**1b. Restart Docker after writing config** so that image pulls and all subsequent operations use the optimized config. This ensures the on-disk state matches the boot-time config.

**1c. Pre-warm Docker state** by running a throwaway container from one of the actual images after pulling:

```bash
docker run --rm awiciroh/datastream:$DS_TAG echo "warm"
```

This forces Docker to fully unpack image layers, create overlay mounts, and write all metadata to disk. When the AMI boots later, this state is already on the EBS snapshot.

### Part 2: Execution Template Changes

Prepend `docker info > /dev/null` as the first command in each execution template. Example:

```json
"commands": [
    "runuser -l ec2-user -c 'docker info > /dev/null'",
    "runuser -l ec2-user -c '... (existing command)'"
]
```

This applies to all 4 datastream templates:
- `cfe-nom/templates/execution_datastream_cfe_nom_VPU_template.json.tpl`
- `forcing/templates/execution_forcing_template.json.tpl`
- `lstm_0/templates/execution_datastream_VPU_template.json.tpl`
- `routing-only/templates/execution_datastream_routing_only_VPU_template.json.tpl`

Purpose:
- Blocks until dockerd is fully responsive before the real workload starts.
- Fails fast with a clear error if Docker is broken, rather than a cryptic `docker run` failure.
- The Commander lambda's regex parsing of `--s3_prefix`, `--s3_bucket` etc. will simply skip this command since it contains none of those patterns.

## Files Changed

| File | Change |
|------|--------|
| `shell/create_ami.sh` | Add daemon.json, restart Docker, pre-warm container |
| `infra/aws/terraform/services/nrds/datastreams/cfe-nom/templates/*.json.tpl` | Prepend `docker info` command |
| `infra/aws/terraform/services/nrds/datastreams/forcing/templates/*.json.tpl` | Prepend `docker info` command |
| `infra/aws/terraform/services/nrds/datastreams/lstm_0/templates/*.json.tpl` | Prepend `docker info` command |
| `infra/aws/terraform/services/nrds/datastreams/routing-only/templates/*.json.tpl` | Prepend `docker info` command |
| `ami_version.yml` | Bump `datastream-ami-version` to trigger new AMI build |

## Risks

- **Low**: The daemon.json settings are all well-established defaults on Amazon Linux 2023. The only risk is if a future Docker update changes default behavior for one of these options.
- **Low**: The `docker info` health check adds a few seconds to each execution but provides diagnostic value.
- **None**: No changes to Lambda functions or state machine logic.

## Expected Impact

- 10-40 second reduction in Docker warm-up time per execution.
- Clearer diagnostics when Docker is unhealthy.
- Exact savings to be measured by comparing execution times before/after the AMI update.
