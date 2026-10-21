# Outputs Diff

`.github/workflows/outputs-diff.yml` answers one question about a change to a datastream:
does it change what the datastream simulates? It runs the change the way production
does (short_range, init 00) and compares the troute output with production's output for
the same date. Then it comments **Same** or **Different** on the branch's open pull
request. The check is informational and never fails.

## When to run it

Outputs Diff only runs manually: from the Actions tab, **Run workflow** on the branch
simulates a chosen datastream and VPUs, or a contribution file.

`.github/workflows/outputs-diff-hint.yml` runs on pull requests and starts nothing on AWS.
When a pull request changes one of these files under `infra/aws/terraform/services/nrds/`,
it comments with the Outputs Diff run to start for each change:

| Change | Suggested run |
|---|---|
| `datastreams/<datastream>/templates/**` or `config/**` | the datastream, on its first VPU |
| a `<datastream>_ami_id` in `envs/prod.tfvars` | the datastream on the new AMI, on its first VPU |
| `datastreams/<datastream>/contributions/<issue>.yml` | the contribution file, on its VPU |

The comment is updated on each push. Only `cfe-nom`, `lstm_0` and `routing-only` run
datastreamcli, so changes to other datastreams get no suggestion.

## How

1. The template is filled in the way `schedules.tf` fills it, with values from
   `config/`, `schedules.tf` and `envs/prod.tfvars`.
2. The run is pinned to yesterday (UTC), forcing included, and its output goes to
   `test/outputs_diff/<run>/<target>`. For a contribution,
   `research_datastream.contribution_parameters check` builds the merged realization.
   That realization is uploaded beside the output, and `-R` points to it.
3. The execution runs on the production state machine.
4. The two troute outputs are joined on `feature_id`, `time` and `type`, and compared with
   `numpy.isclose`. For a contribution, the comment also counts the contributed
   catchments whose flowpaths changed (troute reports `cat-N`'s flowpath as `feature_id`
   N). It warns when none did.
5. The test prefix is deleted.

A comparison is only fair if production ran yesterday with what the branch leaves
unchanged. A change deployed today, such as a new template or realization, shows up as a
difference until tomorrow's run.

## Requirements

The `github-actions-terraform-oidc` role must trust `workflow_dispatch` runs of this
repository's branches. It also needs permission to start and describe executions of the
production state machine, and to read, write and delete under `test/outputs_diff/`. A
pull request from a fork has no branch here to run on, so the hint's command only works
once its changes are pushed to a branch of this repository.
