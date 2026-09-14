# research_datastream_core

Deployment-agnostic core logic for the NextGen Research DataStream (NRDS)
orchestrators. The AWS deployment (`infra/aws/`) drives ephemeral EC2 workers
from a fleet of Lambdas + Step Functions; the LXD deployment (`infra/lxd/`)
drives ephemeral LXD instances from a single always-on controller. The two
share a body of pure, side-effect-free logic — chiefly the rules for turning
the literal `DAILY` token in a run's commands into a concrete forecast date.

This package holds that shared logic so it lives in exactly one place.

## What's here

- `commands.py` — parse a datastream command list (`--s3_prefix`,
  `--forcing_source`, `-F` forcing file) and resolve the `DAILY` token to a
  date, with the same fold-back and MEDIUM_RANGE ensemble hour-shift rules the
  AWS `streamcommander` lambda uses. `substitute_daily(...)` takes an injectable
  `now` so callers can test deterministically.

Stdlib only — no third-party dependencies — so it can be vendored into an AWS
Lambda zip or installed on the LXD controller without dragging in wheels.

## Use

```python
from research_datastream_core import substitute_daily

resolved = substitute_daily(commands, now=datetime.now(timezone.utc))
```

The LXD orchestrator (`research_datastream_lxd`) depends on this package. The
AWS `streamcommander` lambda currently inlines an equivalent of this logic;
it can adopt this package later (vendor it into the lambda zip) without
behavior change.
