"""Orchestrate one scheduled run start-to-finish: launch → execute → check
output → teardown, with retries. Teardown always runs, even on failure.

The AWS deployment splits this across five Lambdas (start_ami, streamcommander,
poller, checker, stopper) driven by Step Functions; here it is one function."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_datastream_core import (
    extract_forcing_source,
    resolve_daily_date,
    substitute_daily,
)

from .config import ScheduledRun
from .lxd import LXDClient

log = logging.getLogger(__name__)

# Failed runs log here too; __main__ optionally attaches a daily-rotating file
# handler (--failure-log). Propagates, so failures still reach the console.
failure_log = logging.getLogger("research_datastream_lxd.failures")


class DatastreamFailure(RuntimeError):
    """Raised to signal a run-level failure that should trigger cleanup + retry."""

DEFAULT_FORWARD_ENV = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_DEFAULT_REGION",
)

# `aws s3` retry tuning injected into every exec so transient
# EndpointConnectionErrors (shared NAT/DNS exhaustion under fan-out) retry
# instead of failing the run. Controller env overrides each default.
AWS_TUNING_ENV_DEFAULTS = {
    "AWS_RETRY_MODE": "standard",
    "AWS_MAX_ATTEMPTS": "10",
}

# max_concurrent_requests has no env var (CLI reads it only from ~/.aws/config),
# so when this is set we prepend an `aws configure set` (see
# _s3_concurrency_prelude). Caps connections = containers x this.
S3_MAX_CONCURRENT_REQUESTS_ENV = "RDS_LXD_S3_MAX_CONCURRENT_REQUESTS"


def _build_environment(execution: dict) -> dict[str, str]:
    """Build the env injected into each instance exec.

    AWS creds: explicit forward_env vars on the controller if set, else the
    active botocore credential chain (AWS_PROFILE, ~/.aws, SSO, ...).
    """
    names = execution.get("run_options", {}).get("forward_env", DEFAULT_FORWARD_ENV)
    env = {name: os.environ[name] for name in names if os.environ.get(name)}
    if "AWS_ACCESS_KEY_ID" not in env:
        env.update(_resolve_aws_credentials())

    for name, default in AWS_TUNING_ENV_DEFAULTS.items():
        env[name] = os.environ.get(name, default)

    if env:
        log.info("forwarding env to instance exec: %s", ", ".join(sorted(env)))
    return env


def _s3_concurrency_prelude() -> list[str]:
    """If RDS_LXD_S3_MAX_CONCURRENT_REQUESTS is set, return a command that caps
    the AWS CLI's parallel-transfer count inside the container. Empty otherwise.
    """
    cap = os.environ.get(S3_MAX_CONCURRENT_REQUESTS_ENV)
    if not cap:
        return []
    try:
        cap_n = int(cap)
    except ValueError:
        log.warning("%s=%r is not an int; ignoring", S3_MAX_CONCURRENT_REQUESTS_ENV, cap)
        return []
    log.info("capping per-container aws s3 max_concurrent_requests to %d", cap_n)
    return [f"aws configure set default.s3.max_concurrent_requests {cap_n}"]


def _resolve_aws_credentials() -> dict[str, str]:
    """Resolve AWS creds from the active botocore session (profile/SSO/env).

    Honors AWS_PROFILE; returns the *frozen* keys so STS/SSO sessions are
    captured as concrete values (incl. AWS_SESSION_TOKEN) at send time.
    """
    try:
        import botocore.session
    except ImportError:
        log.warning("botocore unavailable; cannot resolve AWS creds from a profile")
        return {}
    session = botocore.session.Session()
    creds = session.get_credentials()
    if creds is None:
        log.warning(
            "no AWS credentials found (checked env, AWS_PROFILE=%s, ~/.aws, SSO)",
            os.environ.get("AWS_PROFILE", "<unset>"),
        )
        return {}
    frozen = creds.get_frozen_credentials()
    out = {
        "AWS_ACCESS_KEY_ID": frozen.access_key,
        "AWS_SECRET_ACCESS_KEY": frozen.secret_key,
    }
    if frozen.token:
        out["AWS_SESSION_TOKEN"] = frozen.token
    region = session.get_config_variable("region")
    if region:
        out.setdefault("AWS_DEFAULT_REGION", region)
    log.info(
        "resolved AWS creds via botocore (profile=%s, access_key=%s…)",
        os.environ.get("AWS_PROFILE", "default"), frozen.access_key[:4],
    )
    return out


def _render_template(template_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    """Render a JSON .tpl file (Terraform ${var} syntax) into a dict. Only
    ${name} tokens are subbed — string.Template would mangle JSON's braces."""
    return json.loads(_substitute_tf_vars(template_path.read_text(), context))


_TF_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _substitute_tf_vars(raw: str, context: dict[str, Any]) -> str:
    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in context:
            raise KeyError(f"template variable ${{{key}}} has no value")
        return str(context[key])
    return _TF_VAR.sub(repl, raw)


def run(
    run_spec: ScheduledRun,
    lxd_client: LXDClient | None = None,
    output_check: "OutputCheck | None" = None,
    target: str | None = None,
) -> dict[str, Any]:
    """
    Execute one scheduled datastream run end-to-end.

    `target` pins every launch attempt to a specific cluster member (chosen by
    the scheduler's memory-aware placement); None lets LXD place it.
    """
    lxd_client = lxd_client or LXDClient()
    execution = _render_template(run_spec.template_path, run_spec.context)

    # Prepended once here (not per-attempt) so retries don't stack duplicates.
    execution["commands"] = _s3_concurrency_prelude() + execution.get("commands", [])

    execution.setdefault("run_options", {}).update(run_spec.run_options)
    execution["t0"] = time.time()
    execution["ii_pass"] = False
    execution["ii_s3_object_checked"] = False
    execution["retry_attempt"] = 0

    n_retries = int(execution["run_options"].get("n_retries_allowed", 0))
    timeout_s = int(execution["run_options"].get("timeout_s", 3600))

    for attempt in range(n_retries + 1):
        execution["retry_attempt"] = attempt
        instance_name = f"{run_spec.name}-{int(time.time())}".replace("_", "-")
        log.info(
            "=== %s attempt %d/%d (instance=%s) ===",
            run_spec.name, attempt, n_retries, instance_name,
        )
        try:
            instance = _launch(lxd_client, instance_name, run_spec, execution, target=target)
            _execute(lxd_client, instance, execution, timeout_s)
            if execution["run_options"].get("ii_check_output", False):
                if output_check is None:
                    log.warning("ii_check_output set but no OutputCheck provided")
                else:
                    execution["ii_s3_object_checked"] = output_check.verify(execution)
                    if not execution["ii_s3_object_checked"]:
                        raise DatastreamFailure("output objects not found")
            execution["ii_pass"] = True
            log.info("=== %s SUCCEEDED on attempt %d ===", run_spec.name, attempt)
            return execution
        except Exception as e:  # noqa: BLE001
            log.exception("attempt %d failed: %s", attempt, e)
            execution["failedInput"] = {"error": str(e), "attempt": attempt}
        finally:
            _teardown(lxd_client, instance_name, execution)

    log.error("=== %s FAILED after %d attempts ===", run_spec.name, n_retries + 1)
    _record_failure(run_spec, execution, n_retries + 1)
    return execution


def _classify_failure(execution: dict) -> str:
    """Bucket a terminal failure: no_output (exec ok but objects missing),
    exec_failed (command returned non-zero), or error (anything else)."""
    error = execution.get("failedInput", {}).get("error", "")
    if "output objects not found" in error:
        return "no_output"
    if error.startswith("exec rc="):
        return "exec_failed"
    return "error"


def _record_failure(run_spec: ScheduledRun, execution: dict, attempts: int) -> None:
    """Emit one structured record for a run that failed to produce output.

    Called once, after all retries are exhausted. Goes to the dedicated
    `…failures` logger, whose per-day FileHandler routes it to the failure log.
    Fields are key=value so the file stays both human-readable and greppable
    (e.g. `grep reason=no_output`).
    """
    error = execution.get("failedInput", {}).get("error", "unknown")
    commands = execution.get("commands", [])
    bucket, prefix = _extract_bucket_prefix(commands)
    # Resolve DAILY (left literal by cfe-nom) so failures are attributable to a date.
    date = _forecast_date(commands, execution.get("t0"))
    if prefix and "DAILY" in prefix:
        prefix = prefix.replace("DAILY", date)
    failure_log.error(
        "FAILED_RUN reason=%s date=%s run=%s datastream=%s group=%s init=%s vpu=%s "
        "member=%s attempts=%d instance=%s expected_output=%s error=%r commands=%r",
        _classify_failure(execution), date, run_spec.name, run_spec.datastream,
        run_spec.group, run_spec.init, run_spec.vpu or "-", run_spec.member or "-",
        attempts,
        execution.get("instance_parameters", {}).get("InstanceId", "-"),
        f"s3://{bucket}/{prefix}" if bucket and prefix else "-",
        error,
        commands,
    )


def _forecast_date(commands: list[str], t0: float | None) -> str:
    """Resolve the run's forecast date (YYYYMMDD) via the shared DAILY fold-back,
    keyed off --forcing_source and anchored to the run's launch time (t0)."""
    now = datetime.fromtimestamp(t0, tz=timezone.utc) if t0 else None
    return resolve_daily_date(extract_forcing_source(commands), now=now)


def _launch(lxd: LXDClient, instance_name: str, run_spec: ScheduledRun, execution: dict,
            target: str | None = None) -> Any:

    resources = {**run_spec.resources, **execution.get("instance_parameters", {}).get("Resources", {})}
    image = resources.get("image") or execution.get("instance_parameters", {}).get("Image", "ubuntu:22.04")
    profiles = resources.get("profiles") or ["default"]
    instance = lxd.launch_instance(
        name=instance_name,
        image=image,
        profiles=profiles,
        resources=resources,
        wait=True,
        target=target,
    )
    execution.setdefault("instance_parameters", {})["InstanceId"] = instance_name
    return instance


def _execute(lxd: LXDClient, instance: Any, execution: dict, timeout_s: int) -> None:

    commands = execution.get("commands", [])
    if not commands:
        raise DatastreamFailure("no commands to execute")

    commands = substitute_daily(commands, retry_attempt=execution.get("retry_attempt", 0))
    execution["commands"] = commands

    environment = _build_environment(execution)
    result = lxd.execute(instance, commands, timeout_s=timeout_s, environment=environment)
    if not result.succeeded:
        raise DatastreamFailure(
            f"exec rc={result.exit_code}; stderr tail: {result.stderr[-500:]}"
        )


def _teardown(lxd: LXDClient, instance_name: str, execution: dict) -> None:

    run_options = execution.get("run_options", {})
    if not run_options.get("ii_terminate_instance", True):
        log.info("ii_terminate_instance=False; leaving %s in place", instance_name)
        return
    lxd.stop_and_delete(
        instance_name,
        delete_disk=run_options.get("ii_delete_volume", True),
    )


class OutputCheck:
    """Protocol: `verify(execution) -> bool`. Default impls below."""
    def verify(self, execution: dict) -> bool:  # pragma: no cover
        raise NotImplementedError


class S3OutputCheck(OutputCheck):
    """Port of checker.lambda_handler — check an S3 prefix appeared.

    Only imported lazily so deployments with no S3 sink don't need boto3.
    """
    def __init__(self, region: str = "us-east-1") -> None:
        import boto3  # noqa: PLC0415
        self._s3 = boto3.client("s3", region_name=region)

    def verify(self, execution: dict) -> bool:
        bucket, prefix = _extract_bucket_prefix(execution.get("commands", []))
        if not bucket or not prefix:
            log.warning("no bucket/prefix in commands; skipping output check")
            return False
        # forcing writes metadata.csv; ngen-run writes ngen-run.tar.gz
        key = (
            f"{prefix}/ngen-run.tar.gz"
            if any("/scripts/datastream" in c for c in execution["commands"])
            else f"{prefix}/metadata/forcings_metadata/metadata.csv"
        )
        log.info("checking s3://%s/%s", bucket, key)
        for _ in range(10):
            resp = self._s3.list_objects_v2(Bucket=bucket, Prefix=key)
            if "Contents" in resp:
                return True
            time.sleep(1)
        return False


def _extract_bucket_prefix(commands: list[str]) -> tuple[str | None, str | None]:
    bucket = prefix = None
    for c in commands:
        m = re.search(r"(?i)--s3_bucket[=\s']+([^\s']+)", c)
        if m:
            bucket = m.group(1)
        m = re.search(r"(?i)--s3_prefix[=\s']+([^\s']+)", c)
        if m:
            prefix = m.group(1)
    return bucket, prefix
