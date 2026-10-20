# research_datastream

Python tools for working with NextGen Research DataStream (NRDS) data that do
not depend on how the datastream is deployed. Code that runs or provisions the
datastream lives under `infra/`:

| Package | Location | Purpose |
| --- | --- | --- |
| `research_datastream` | `python/` (here) | Deployment-agnostic tools: contributions, health checks, plots, S3 utilities |
| `research_datastream_core` | `infra/common/python/` | Logic shared by the AWS and LXD orchestrators |
| `research_datastream_aws` | `infra/aws/python/` | AWS-only tooling (cost reporting, VPU test executions) |
| `research_datastream_lxd` | `infra/lxd/python/` | LXD orchestrator and scheduler |

## Install

```bash
pip install -e python            # contribution_parameters, s3mv
pip install -e "python[plots]"   # adds nrds_run_health, vpu_comparison_graphs
```

## What's here

- `contribution_parameters` — validate (`check`) and deploy (`deploy`) a
  community parameter contribution. Run by `.github/workflows/contribution.yml`.
  ```bash
  python -m research_datastream.contribution_parameters check <contribution.yml> --out cand.json
  ```
- `nrds_run_health` — check which runs landed in the public bucket over a date
  range and chart the results.
  ```bash
  python -m research_datastream.nrds_run_health --start 20251001 --end 20251007 --vpus all
  ```
- `vpu_comparison_graphs` — plot per-VPU performance from run profile metadata.
  ```bash
  python -m research_datastream.vpu_comparison_graphs -d 20251009 -r short_range -t 14
  ```
- `s3mv` — multithreaded move of objects between S3 prefixes.
  ```bash
  python -m research_datastream.s3mv --help
  ```
