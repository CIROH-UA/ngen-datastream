# research_datastream_aws

AWS-specific tooling for the NextGen Research DataStream. Deployment-agnostic
tools (contributions, health checks, plots) live in the root [`python/`](../../../python) package.

- `datastream_cost_nrds` — report what the AWS deployment costs over a time window.

```bash
pip install -e infra/aws/python
python -m research_datastream_aws.datastream_cost_nrds --help
```
