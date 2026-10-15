# Outputs Diff

`.github/workflows/outputs-diff.yml` answers one question for a change to a datastream:
does it change what the datastream simulates? It runs the change the way production
runs it and compares the troute output with production's own output for the same date,
then comments **Same** or **Different** on the pull request. It is informational and
never fails, so it never blocks a merge.

## What it simulates

On a pull request, any change to these files under
`infra/aws/terraform/services/nrds/`:

| Change | Simulated as |
|---|---|
| `datastreams/<datastream>/templates/**`, `config/**` | this branch's template, for the datastream's first VPU |
| a datastream's `<datastream>_ami_id` in `envs/prod.tfvars` | this branch's template on the new AMI, for the datastream's first VPU |
| `datastreams/<datastream>/contributions/<issue>.yml` | this branch's template, with the merged realization in place of the live one, for the contribution's VPU |

Only `cfe-nom`, `lstm_0` and `routing-only` run datastreamcli. A change to `forcing`,
`qkrig` or `restart` is listed in the comment as not simulated.

From the Actions tab, **Run workflow** simulates a chosen datastream and VPUs (or
`all`), or a contribution file, which overrides both. A manual run comments on the
branch's open pull request when it has one, and otherwise writes only the job summary.
`dry_run` renders the execution and launches nothing.

## How a target runs

1. **Render.** `.github/outputs-diff/render` renders the branch's template through
   terraform's `templatefile()`, with the variables `schedules.tf` passes.
2. **Pin.** The run is pinned to the most recent date with production troute output
   (or `baseline_date`), and `--S3_PREFIX` is moved to
   `test/outputs_diff/<run id>/<target>`.
3. **Contribution.** `research_datastream.contribution_parameters check` builds the
   merged realization, the same check the Parameter Contribution workflow runs. The
   realization is uploaded under the test prefix and named by `-R`. The divides whose
   catchment entries it changes are recorded, since `cat-N` is reported by troute as
   `feature_id` N.
4. **Run.** The execution goes to the production Step Functions state machine.
5. **Compare.** Baseline and test parquet are joined on `feature_id`, `time` and
   `type`, and each column is compared at `rtol`/`atol`. For a contribution, the
   comment also counts the contributed catchments whose flowpaths changed, and warns
   when none did: the parameters were accepted but had no effect.
6. **Clean up.** The test prefix is deleted.

The baseline is only a fair comparison if production ran the same realization. When
the live realization was modified on or after the baseline date, the comment notes
that the baseline may reflect an earlier one.

## Reading the comment

| Outputs | Meaning |
|---|---|
| 🟰 Same | every compared value is equal, or within tolerance |
| 🔀 Different | some value, or the set of rows, differs |
| ❌ Could not compare | the target failed before comparing; the detail names the step |

## Requirements

The `github-actions-terraform-oidc` role must trust `pull_request` runs of this
repository, and allow `states:StartExecution`/`DescribeExecution` on the production
state machine and S3 read, write and delete under `test/outputs_diff/`. A pull request
from a fork gets no OIDC token or write token, so its targets report
**Could not compare** and no comment is posted.
