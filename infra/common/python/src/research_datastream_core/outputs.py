"""Where a run's completion marker lands in S3. Shared by the AWS checker
lambda and the LXD output check, which each do the S3 lookup themselves."""

from __future__ import annotations

import re

from .commands import extract_s3_bucket, extract_s3_prefix

__all__ = ["is_datastream_run", "output_marker"]

_DATASTREAM_RE = re.compile(r"(?i)/scripts/datastream[=\s']+([^\s']+)")


def is_datastream_run(commands: list[str]) -> bool:
    """True when the commands call datastreamcli (an ngen run), False for the
    forcing generator and other jobs."""
    return any(_DATASTREAM_RE.search(c) for c in commands)


def output_marker(commands: list[str]) -> tuple[str, str] | None:
    """Return ``(bucket, key)`` of the object a successful run writes last, or
    None when the commands have no S3 sink.

    datastreamcli writes ``merkdir.file`` after its upload; the forcing
    generator writes ``metadata/forcings_metadata/metadata.csv``. ``key`` is a
    prefix to list, not an exact key. Call this on commands whose ``DAILY``
    tokens are already resolved.
    """
    bucket = extract_s3_bucket(commands)
    prefix = extract_s3_prefix(commands)
    if bucket is None or prefix is None:
        return None
    if is_datastream_run(commands):
        return bucket, f"{prefix}/merkdir.file"
    return bucket, f"{prefix}/metadata/forcings_metadata/metadata.csv"
