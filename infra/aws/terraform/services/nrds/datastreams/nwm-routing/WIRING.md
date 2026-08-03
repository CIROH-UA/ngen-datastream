# nwm-routing datastream — local draft (NOT wired, NOT applied)

NRDS wrapper for the improved routing-only pipeline (route on NWM fabric with
t-route, convert to NextGen IDs after). Three containers per run:

1. `awiciroh/routing-only-preprocess` — fetch CHRTOUT + AA from GCS, rename,
   generate restart + crosswalk, render troute.yaml (repo:
   AlabamaWaterInstitute/routing-comparison-nwm-nextgen-troute, may move to BYU org)
2. `awiciroh/ciroh-ngen-image:v1.7.0` — t-route routing (`-m nwm_routing -f -V4`).
   Stock image validated bit-identical to the nhd_io-patched build on 2026-08-03,
   warm start verified via cold-start control + restart perturbation test.
3. `awiciroh/routing-only-postprocess` — NWM→NextGen conversion, NRDS-schema parquet

## Do not apply until

- [ ] Repo org decision settled (AWI vs BYU) — Quinn said hold
- [ ] Both images pushed to Docker Hub with pinned tags; update
      `config/execution_forecast_inputs_nwm_routing.json` `images` block to match
- [ ] S3 prefix `outputs/nwm_routing/` blessed by team
- [ ] One manual SM execution validated (same procedure as the 2026-07-20
      routing-only test: clone input, redirect prefix to `test_runs/`, verify S3)

## Wiring — add to services/nrds/main.tf

```hcl
module "nwm_routing_schedules" {
  source = "./datastreams/nwm-routing"

  region               = var.region
  state_machine_arn    = module.nrds_orchestration.datastream_arn
  scheduler_role_arn   = aws_iam_role.scheduler_role.arn
  ec2_instance_profile = module.nrds_orchestration.ec2_instance_profile_name

  ami_id = var.ami_id # the ngen datastream AMI — has docker, NGIAB v1.7.0, merkdir pre-pulled

  schedule_timezone   = var.schedule_timezone
  schedule_group_name = var.schedule_group_name
  environment_suffix  = var.environment_suffix
}
```

## Design notes (why the template looks the way it does)

- **DAILY resolution**: because the parser hint sets `--forcing_source`, the
  streamcommander lambda does NOT do generic standalone-DAILY replacement in
  commands (that only happens when forcing_source is None — the qkrig path).
  It replaces DAILY only inside occurrences of the exact `--s3_prefix` string.
  So commands that need the date embed the full prefix and extract the 8-digit
  date after substitution (`grep -oE "[0-9]{8}" | head -1`). The forcing_source
  hint also sets the init-hour cutoff so DAILY resolves to today, not yesterday.
- **`-f` in the routing command** matches the lambda's case-insensitive `-F`
  forcing-file regex (captures `-V4`), but is harmless: SHORT_RANGE means no
  ensemble shift, and no literal `-F` appears in any command, so no substitution
  fires. Avoid adding `[ -f ... ]` tests or other `-f`/`-F` flags to commands
  (qkrig bug #6) — use `[ -e ]` / `[ -n ]`.
- **merkdir + `ii_check_s3: true`**: the checker (post-#381) requires
  `<prefix>/merkdir.file`; generated with the same zwills/merkdir invocation
  datastreamcli uses. If merkdir proves flaky, flip `ii_check_s3` to false
  (qkrig posture) rather than deleting the step.
- **Both .nc and converted parquet uploaded** under `ngen-run/outputs/troute/`
  (mirrors routing-only layout). The 45 MB NWM-native .nc × 24 cycles ≈ 1 GB/day
  if all cycles enabled — revisit before CONUS/all-init expansion.
- **Pilot scope**: init 12 only, VPU 03W only (matches the validated local run).
  Expand `init_cycles` in config after the first clean scheduled runs.
- **nprocs = 4 on m8g.xlarge (4 vCPU)** — sized to match, unlike the
  routing-only module's known 4-on-2-vCPU oversubscription.
