# Outputs Diff

`.github/workflows/outputs-diff.yml` answers one question about a change to a datastream:
does it change what the datastream simulates? It runs the change the way production
does (short_range, init 00) and compares the troute output with production's output for
the same date. Then it comments **Same** or **Different** on the pull request. The check
is informational and never fails.

## What it simulates

On a pull request, a change to any of these files under `infra/aws/terraform/services/nrds/`:

| Change | Simulated as |
|---|---|
| `datastreams/<datastream>/templates/**` or `config/**` | this branch's template, on the datastream's first VPU |
| a `<datastream>_ami_id` in `envs/prod.tfvars` | this branch's template on the new AMI, on the datastream's first VPU |
| `datastreams/<datastream>/contributions/<issue>.yml` | this branch's template with the merged realization, on the contribution's VPU |

Only `cfe-nom`, `lstm_0` and `routing-only` run datastreamcli, so changes to other
datastreams are not simulated. From the Actions tab, **Run workflow** simulates a chosen
datastream and VPUs, or a contribution file. A manual run comments on the branch's open
pull request if there is one.

## How

1. The template is filled in the way `schedules.tf` fills it, with values from
   `config/`, `schedules.tf` and `envs/prod.tfvars`.
2. The run is pinned to yesterday, or to `baseline_date`, and its output goes to
   `test/outputs_diff/<run>/<target>`. For a contribution,
   `research_datastream.contribution_parameters check` builds the merged realization.
   That realization is uploaded beside the output, and `-R` points to it.
3. The execution runs on the production state machine.
4. The two troute outputs are joined on `feature_id`, `time` and `type`, and compared with
   `numpy.isclose`. For a contribution, the comment also counts the contributed
   catchments whose flowpaths changed (troute reports `cat-N`'s flowpath as `feature_id`
   N). It warns when none did.
5. The test prefix is deleted.

A comparison is only fair if production ran the live realization on the baseline date.
If a realization was deployed after that date, rerun with a later `baseline_date`.

## Requirements

The `github-actions-terraform-oidc` role must trust `pull_request` runs. It also needs
permission to start and describe executions of the production state machine, and to
read, write and delete under `test/outputs_diff/`. Pull requests from forks get no OIDC
token, so their targets report **Could not compare**.
