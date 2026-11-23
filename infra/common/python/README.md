# research_datastream_core

Logic shared by the NextGen Research DataStream (NRDS) orchestrators. The AWS
deployment (`infra/aws/`) drives ephemeral EC2 workers from Lambdas + Step
Functions; the LXD deployment (`infra/lxd/`) drives ephemeral LXD instances
from one always-on controller. Both make the same decisions about a run's
commands, and those decisions live here so a fix lands in one place.

## What's here

- `commands.py` — parse a datastream command list (`--s3_bucket`,
  `--s3_prefix`, `--forcing_source`, `-F` forcing file) and resolve the `DAILY`
  token to a date: the forecast-cycle fold-back, the MEDIUM_RANGE ensemble
  hour shift, and dating the output prefix at launch.
- `commands.py` also lists a run's dynamic inputs (`-F` forcing, `-t` restart)
  that must exist before launch, and resolves `{DAILY[+-Nh]:YYYYMMDD|HH}`
  tokens, e.g. `{DAILY-28h:HH}` for the analysis_assim_extend restart hour.
- `backoff.py` — wait timing: the exponential wait between input checks
  before launch (`input_wait_*` run options, 24 h timeout) and before
  retrying a failed run (`retry_backoff_*`).
- `outputs.py` — the S3 object a finished run writes last (`merkdir.file` for
  datastreamcli, `metadata.csv` for the forcing generator), which both
  orchestrators check before calling a run a success.

## Who uses it

| Caller | How it gets the package |
| --- | --- |
| AWS `input_gate`, `streamcommander`, `checker` and `stopper` lambdas | Copied into each lambda zip by `infra/aws/terraform/modules/orchestration/lambda.tf` |
| LXD controller (`research_datastream_lxd`) | `pip install` from git in `infra/lxd/terraform/cloud-init.yaml.tftpl` |

A change here redeploys the AWS lambdas (the Terraform workflows watch
`infra/common/python/src/**`). The LXD controller picks it up when it is
reinstalled at its `package_ref`.

## What belongs here

Put logic here when both deployments must agree on it: how a command is
interpreted, what date a run is for, which inputs it needs, how long to wait
between checks and retries, what counts as success. Keep out anything that
depends on how a deployment runs things: launching instances, sleeping,
teardown, credentials. Those stay in each deployment so either one can change
without touching the other.

The package is stdlib only, with no I/O. Callers pass in `now` and do their own
S3 calls, so it runs unchanged inside a Lambda and on the controller.

## Use

```python
from research_datastream_core import output_marker, substitute_daily

commands = substitute_daily(commands, now=datetime.now(timezone.utc))
bucket, key = output_marker(commands)
```

## Test

```bash
pip install -e "infra/common/python[test]"
pytest infra/common/python
```
