# NRDS on LXD

LXD deployment of the NextGen Research DataStream (NRDS). The sibling
`infra/aws/` deployment uses EventBridge + Step Functions + five Lambdas
to orchestrate ephemeral EC2 workers. This deployment collapses that
architecture to one always-on LXD "controller" instance that hosts a
Python process combining the scheduler and orchestrator. Ephemeral
worker instances are still launched per run; only the glue changed.

```
                     +---------------------------------------+
                     |       controller (LXD instance)       |
   cron time  --->   |   APScheduler  -->  runner.run(spec)  |
                     |                          |            |
                     |                          v            |
                     |                    pylxd API calls    |
                     +------------|----------|---------------+
                                  v          v
                     +------------+----------+---------------+
                     |  ephemeral worker (per scheduled run) |
                     +---------------------------------------+
```

## Layout

```
infra/common/python/                  # shared, deployment-agnostic core logic
└── src/research_datastream_core/
    └── commands.py                   # DAILY-token resolution (AWS + LXD share this)

infra/lxd/
├── python/                       # the orchestrator + scheduler process
│   └── src/research_datastream_lxd/
│       ├── __main__.py           # `python -m research_datastream_lxd`
│       ├── config.py             # YAML loader → ScheduledRun objects
│       ├── scheduler.py          # APScheduler; EventBridge replacement
│       ├── runner.py             # launch → exec → check → teardown
│       └── lxd.py                # pylxd wrapper
│
└── terraform/
    ├── main.tf                   # provider, controller, config push
    ├── variables.tf
    ├── outputs.tf
    ├── cloud-init.yaml.tftpl     # installs packages + systemd unit
    ├── envs/{prod.tfvars, prod.backend.hcl}
    └── datastreams/              # one datastream = one YAML + template(s)
        ├── forcing/              # VPUs split inside one command
        │   ├── forcing.yaml
        │   └── templates/execution_forcing.json.tpl
        └── cfe-nom/              # fans out one ngen run per (init, vpu[, member])
            ├── cfe-nom.yaml
            └── templates/execution_cfe_nom.json.tpl
```

`research_datastream_core` holds logic that is identical across the AWS and
LXD deployments — currently the `DAILY` → forecast-date substitution rules
(ported from the AWS `streamcommander` lambda). The LXD package depends on it;
the AWS lambda still inlines an equivalent and can adopt it later.

## What maps to what (AWS → LXD)

| AWS                                               | LXD                                           |
|---------------------------------------------------|-----------------------------------------------|
| `aws_scheduler_schedule` (EventBridge)            | APScheduler jobs in `scheduler.py`            |
| `aws_sfn_state_machine`                           | The `run()` function in `runner.py`           |
| `start_ami` lambda                                | `runner._launch` + `lxd.launch_instance`      |
| `streamcommander` + `poller` lambdas              | `runner._execute` + `lxd.execute`             |
| `checker` lambda                                  | `runner.OutputCheck` (e.g. `S3OutputCheck`)   |
| `stopper` lambda                                  | `runner._teardown` + `lxd.stop_and_delete`    |
| `iam_{ec2,lambda,statemachine,scheduler}.tf`      | one LXD trust token (shared trust store)      |
| `lambda.tf`                                       | `lxd_instance.controller` in `main.tf`        |
| `security_group.tf`                               | `default` profile (NIC) + per-worker `security.nesting` |
| EC2 AMI                                           | LXD image alias (default: `ubuntu:22.04`)     |
| EC2 `InstanceType` (e.g. `m8g.2xlarge`)           | `limits.cpu` + `limits.memory` per worker     |
| EBS volume                                        | LXD root disk device                          |

## Build the deployment from scratch (local host)

The goal: from a fresh laptop with no tooling installed, end up with a
running controller on a target LXD server that fires forcing runs on
cron.

### 0. Prerequisites to install locally

- Terraform ≥ 1.5 — `brew install terraform` / `apt install terraform`
- The `lxc` client (ships with LXD snap/apt) — `sudo snap install lxd` on Ubuntu, or `brew install lxc` on macOS
- Python ≥ 3.10 + `pip` — for building and publishing the orchestrator package
- Credentials on the target LXD server: either admin shell access, or a trust token already issued to you

### 1. Get an LXD endpoint + trust token

If you're the LXD admin, SSH to a cluster node and run:

```bash
# one time, if the API isn't already on the network
lxc config set core.https_address '[::]:8443'

# every time a new client needs access
lxc config trust add --name laptop-$(whoami)
# -> prints a base64 token; single-use, expires in ~1 week
```

If you're not the admin, ask whoever runs the cluster for the endpoint
(`https://host:8443`) and a trust token. Don't open 8443 on a shared
research cluster without talking to them first.

Test it locally:

```bash
lxc remote add nextstream https://<host>:8443 --token <token>
lxc remote switch nextstream
lxc list                 # should return without a cert error
```

### 2. Choose how the controller gets the Python package

By default the controller's cloud-init pip-installs the orchestrator and shared
core package straight from this git repo at `var.package_ref` — no publishing
step needed. Just set `package_ref` to a tag/branch/commit (step 3).

Alternatives, if you'd rather not install from git at boot:
- **Pre-bake into a custom LXD image** and point `controller_image` at it
  (best for production).
- **Publish to an internal PyPI** (`python -m build && twine upload`) and edit
  `cloud-init.yaml.tftpl` to install the pinned version instead.

### 3. Configure `envs/prod.tfvars`

```bash
cd infra/lxd/terraform
$EDITOR envs/prod.tfvars
```

Set at minimum:

- `lxd_endpoint` — what you tested with `lxc remote add`
- `lxd_project`, `lxd_network`, `lxd_storage_pool` — ask the admin, or
  `lxc project list` / `lxc network list` / `lxc storage list`
- `environment_suffix` — e.g. `prod`, `dev`
- `output_check` — `s3` if you want the S3 checker wired up, else `none`
- `package_ref` — git tag/branch/commit the controller installs from

The trust token itself is sensitive and goes in an env var, not the
tfvars file:

```bash
export TF_VAR_lxd_trust_token='<token from step 1>'
```

### 4. Initialize and apply Terraform

```bash
terraform init -backend-config=envs/prod.backend.hcl
terraform plan  -var-file=envs/prod.tfvars
terraform apply -var-file=envs/prod.tfvars
```

What this creates:

- one `lxd_instance.rds-controller-<env>` — the always-on orchestrator
- file pushes: every `datastreams/**` file copied into
  `/etc/research-datastream-lxd/datastreams/` on the controller
- a `local-exec` that restarts the systemd unit whenever config changes

Ephemeral workers are launched by the controller under the LXD `default`
profile (which supplies their network); `security.nesting` is set on each
worker at launch for the podman-in-LXD container runtime.

### 5. Verify it's running

```bash
# is the controller up?
lxc --project <project> list | grep rds-controller

# is the scheduler running?
lxc --project <project> exec rds-controller-prod -- \
    systemctl status research-datastream-lxd

# what jobs are registered?
lxc --project <project> exec rds-controller-prod -- \
    journalctl -u research-datastream-lxd --since "10 minutes ago" | grep registered
```

You should see one log line per scheduled run: 29 for the forcing
datastream (24 short-range + 4 medium-range + 1 AnA), plus 580 for
cfe-nom (24×20 short-range + 4×20×1 medium-range + 1×20 AnA, one run per
VPU per init).

### 6. Fire one run manually (bypasses the scheduler)

```bash
lxc --project <project> exec rds-controller-prod -- \
    /opt/rds-lxd/venv/bin/python -m research_datastream_lxd \
    --once forcing:short_range:06
```

The `--once` selector is `<datastream>[:<group>[:<init>]]`. Omitting
`<init>` or `<group>` means "run all matching," but only if the match
is unique; multi-match selectors exit with a list.

### 7. Adding a datastream

Drop a new directory under `terraform/datastreams/`:

```
terraform/datastreams/cfe-nom/
├── cfe-nom.yaml                             # schedule groups + resources
└── templates/execution_cfe_nom.json.tpl     # the command template
```

then `terraform apply` again. The file-push resource picks up new files
automatically; the `local-exec` restarts the scheduler so the new jobs
register.

No Python changes are required for new datastreams. A datastream whose
orchestration genuinely diverges from launch→exec→check→teardown would
need runner changes, but that's not what a new datastream usually is.

### 8. Teardown

```bash
terraform destroy -var-file=envs/prod.tfvars
```

This removes the controller. Any ephemeral worker instances currently
running at destroy time are orphaned; the
controller's `stop_and_delete` would have handled them at end-of-run.
If you're destroying mid-run, clean up with
`lxc list | grep <env>` followed by `lxc delete -f <name>`.

## Developing the orchestrator

Install the package locally and fire a single run before pushing:

```bash
cd infra/lxd/python
pip install -e ../../common/python   # shared core; not on PyPI, install first
pip install -e .
python -m research_datastream_lxd \
    --datastreams-dir ../terraform/datastreams \
    --once forcing:short_range:06

# per-VPU datastreams take extra selector segments: DATASTREAM:GROUP:INIT:VPU[:MEMBER]
python -m research_datastream_lxd \
    --datastreams-dir ../terraform/datastreams \
    --once cfe-nom:short_range:06:05
```

For development against a real LXD without touching production:

```bash
# local LXD on your laptop
sudo snap install lxd && sudo lxd init --auto
# point the orchestrator at it by running with LXD_* env unset and
# letting pylxd use the local unix socket
```

## Known limitations / TODO

- **No state persistence across controller restarts.** If the
  controller is restarted mid-run, the in-flight run is lost. The AWS
  version has the same property (a Lambda crash mid-step triggers
  Step Functions retry), but ours doesn't have the retry safety net.
  Add a small SQLite log in `runner.py` if this matters.
- **One controller.** There's no HA. For a research workload hitting a
  shared HPC this is fine; for anything production-critical, two
  controllers with leader election (or just one controller + external
  cron-as-a-failsafe) would be the next step.
