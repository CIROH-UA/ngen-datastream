"""Resolve the literal ``DAILY`` token in datastream commands to a forecast
date (``YYYYMMDD``). The rules differ for the forcing generator vs. ngen runs.
Shared by the AWS streamcommander lambda and the LXD controller. Pure stdlib;
``now`` is injectable for deterministic tests."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

__all__ = [
    "extract_s3_prefix",
    "extract_forcing_source",
    "extract_forcing_file",
    "daily_fcst_cycle",
    "resolve_daily_date",
    "substitute_daily",
]

_S3_PREFIX_RE = re.compile(r"(?i)--s3_prefix[=\s']+([^\s']+)")
_FORCING_SOURCE_RE = re.compile(r"(?i)--forcing_source[=\s']+([^\s']+)")
_FORCING_FILE_RE = re.compile(r"(?i)-F[=\s']+([^\s']+)")
_STANDALONE_DAILY_RE = re.compile(r"(?<![A-Za-z0-9])DAILY(?![A-Za-z0-9])")


def extract_s3_prefix(commands: list[str]) -> str | None:
    """Return the last ``--s3_prefix`` value found across the commands."""
    return _last_match(commands, _S3_PREFIX_RE)


def extract_forcing_source(commands: list[str]) -> str | None:
    """Return the ``--forcing_source`` value, e.g. ``NWM_V3_MEDIUM_RANGE_00_1``.

    The full token including any trailing ``_<member>`` is returned, which the
    MEDIUM_RANGE fold-back relies on (``[-4:-2]`` lands on the cycle digits).
    """
    return _last_match(commands, _FORCING_SOURCE_RE)


def extract_forcing_file(commands: list[str]) -> str | None:
    """Return the ``-F`` forcing-file path, or None if no ngen run is present."""
    return _last_match(commands, _FORCING_FILE_RE)


def _last_match(commands: list[str], pattern: re.Pattern[str]) -> str | None:
    found = None
    for c in commands:
        m = pattern.search(c)
        if m:
            found = m.group(1)
    return found


def daily_fcst_cycle(forcing_source: str | None) -> int:
    """Forecast cycle hour used for the date fold-back.

      * SHORT_RANGE                -> last 2 digits of the source
      * MEDIUM_RANGE               -> digits [-4:-2] (skips the member suffix)
      * ANALYSIS_ASSIM_RESTART_CHRT-> last 2 digits
      * analysis_assim_extend / other forcing source -> 16
      * no forcing source at all   -> 24
    """
    if not forcing_source:
        return 24
    if "SHORT_RANGE" in forcing_source:
        return int(forcing_source[-2:])
    if "MEDIUM_RANGE" in forcing_source:
        return int(forcing_source[-4:-2])
    if "ANALYSIS_ASSIM_RESTART_CHRT" in forcing_source:
        return int(forcing_source[-2:])
    return 16


def resolve_daily_date(forcing_source: str | None, now: datetime | None = None) -> str:
    """Resolve the run date (``YYYYMMDD``) with the fcst-cycle fold-back.

    If the current UTC hour is earlier than the forecast cycle, the cycle has
    not been published yet today, so fold back to yesterday.
    """
    now = now or datetime.now(timezone.utc)
    if now.hour < daily_fcst_cycle(forcing_source):
        now -= timedelta(days=1)
    return now.strftime("%Y%m%d")


def substitute_daily(
    commands: list[str],
    now: datetime | None = None,
    retry_attempt: int = 0,
) -> list[str]:
    """Resolve the literal ``DAILY`` token in a command list to a date.

    Behavior by command shape:
      * No ``--forcing_source``: resolve every standalone ``DAILY``.
      * ``--s3_prefix`` without ``-F``: resolve ``DAILY`` in the prefix (forcing
        generator). With ``-F`` present (ngen runs) leave it literal for
        datastreamcli to expand.
      * ``-F`` forcing file: always resolve, applying the MEDIUM_RANGE ensemble
        hour shift (6h per member beyond the first).

    First attempt only — the hour-shift isn't idempotent, so retries reuse the
    already-resolved commands.
    """
    if retry_attempt != 0:
        return list(commands)

    prefix = extract_s3_prefix(commands)
    forcing_source = extract_forcing_source(commands)
    forcing_file = extract_forcing_file(commands)
    today = resolve_daily_date(forcing_source, now=now)

    out = list(commands)

    # --- --s3_prefix DAILY handling -------------------------------------
    if prefix and "DAILY" in prefix:
        if forcing_source is None:
            out = [_STANDALONE_DAILY_RE.sub(today, c) for c in out]
        elif forcing_file is None:
            # Forcing generator (no -F): date the output prefix in place.
            prefix_dated = prefix.replace("DAILY", today)
            out = [c.replace(prefix, prefix_dated) for c in out]
        # else: -F present → leave the prefix's DAILY literal for datastreamcli.

    # --- -F forcing file DAILY handling + ensemble hour shift -----------
    if forcing_file is not None:
        shifted = forcing_file
        date_for_file = today
        if forcing_source and "MEDIUM_RANGE" in forcing_source:
            ensemble_member = int(forcing_source[-1])
            nhrs_shift = 6 * (ensemble_member - 1)
            m = re.search(r"/(\d{2})/.*?t(\d{2})z", forcing_file)
            if m and nhrs_shift:
                hh_folder = int(m.group(1))
                new_hour = (hh_folder - nhrs_shift) % 24
                if hh_folder - nhrs_shift < 0:
                    # Shifting before midnight rolls the file's date back too.
                    date_for_file = (
                        datetime.strptime(today + m.group(1) + "00", "%Y%m%d%H%M")
                        - timedelta(hours=nhrs_shift)
                    ).strftime("%Y%m%d")
                shifted = re.sub(r"/\d{2}/", f"/{new_hour:02d}/", forcing_file, count=1)
                shifted = re.sub(r"t\d{2}z", f"t{new_hour:02d}z", shifted, count=1)
        replacement = shifted.replace("DAILY", date_for_file)
        out = [c.replace(forcing_file, replacement, 1) if "-F" in c else c for c in out]

    return out
