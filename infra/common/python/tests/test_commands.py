"""Tests for the shared DAILY-token resolution logic (research_datastream_core).

These lock in parity with the AWS streamcommander lambda the logic was ported
from: the forecast-cycle fold-back, the MEDIUM_RANGE ensemble hour-shift, and
the rule that ngen runs (`-F` present) keep `--S3_PREFIX`'s DAILY literal for
datastreamcli to expand while the `-F` path is resolved here.
"""

from datetime import datetime, timezone

import pytest

from research_datastream_core import (
    daily_fcst_cycle,
    extract_forcing_file,
    extract_forcing_source,
    extract_s3_prefix,
    resolve_daily_date,
    substitute_daily,
)

UTC = timezone.utc
NOON = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


# ---- extraction --------------------------------------------------------

def test_extract_last_match_wins():
    assert extract_s3_prefix(["--s3_prefix a/first", "--s3_prefix b/second"]) == "b/second"


def test_extract_forcing_source_keeps_member_suffix():
    cmds = ["... --forcing_source NWM_V3_MEDIUM_RANGE_06_1 ..."]
    assert extract_forcing_source(cmds) == "NWM_V3_MEDIUM_RANGE_06_1"


def test_extract_forcing_file_none_when_absent():
    assert extract_forcing_file(["docker run --forcing_source X"]) is None


def test_extract_forcing_file_present():
    cmds = ["datastream -s DAILY -F s3://b/ngen.DAILY/f/06/ngen.t06z.nc --S3_BUCKET b"]
    assert extract_forcing_file(cmds) == "s3://b/ngen.DAILY/f/06/ngen.t06z.nc"


# ---- forecast cycle ----------------------------------------------------

@pytest.mark.parametrize("source,expected", [
    ("NWM_V3_SHORT_RANGE_06", 6),
    ("NWM_V3_SHORT_RANGE_23", 23),
    ("NWM_V3_MEDIUM_RANGE_12_1", 12),               # [-4:-2] skips the member suffix
    ("NWM_V3_ANALYSIS_ASSIM_RESTART_CHRT_08", 8),
    ("NWM_V3_ANALYSIS_ASSIM_EXTEND", 16),           # any other source -> 16
    (None, 24),                                      # no source -> 24
])
def test_daily_fcst_cycle(source, expected):
    assert daily_fcst_cycle(source) == expected


# ---- date fold-back ----------------------------------------------------

def test_resolve_daily_date_before_cycle_folds_back():
    # SHORT_RANGE_12 -> cycle 12; at 06:00 UTC the cycle isn't out yet -> yesterday
    now = datetime(2026, 7, 1, 6, 0, tzinfo=UTC)
    assert resolve_daily_date("NWM_V3_SHORT_RANGE_12", now=now) == "20260630"


def test_resolve_daily_date_after_cycle_is_today():
    now = datetime(2026, 7, 1, 18, 0, tzinfo=UTC)
    assert resolve_daily_date("NWM_V3_SHORT_RANGE_12", now=now) == "20260701"


# ---- substitute_daily --------------------------------------------------

def test_standalone_daily_no_forcing_source_always_folds_back():
    # No --forcing_source -> cycle 24, so any hour < 24 -> yesterday (mirrors AWS).
    cmds = ["echo run for DAILY", "--s3_prefix out/DAILY/x"]
    assert substitute_daily(cmds, now=NOON) == [
        "echo run for 20260630",
        "--s3_prefix out/20260630/x",
    ]


def test_forcing_generator_dates_prefix_in_place():
    # --s3_prefix DAILY, no -F, forcing_source present -> date the output prefix.
    cmds = ["configure --forcing_source NWM_V3_SHORT_RANGE_00 "
            "--s3_prefix fc/ngen.DAILY/forcing_short_range/00"]
    out = substitute_daily(cmds, now=NOON)[0]
    assert "fc/ngen.20260701/forcing_short_range/00" in out


def test_ngen_run_keeps_prefix_daily_literal_but_resolves_forcing_file():
    cmds = ["datastream -s DAILY -F s3://b/ngen.DAILY/forcing_short_range/06/"
            "ngen.t06z.short_range.forcing.f001_f018.VPU_01.nc "
            "--FORCING_SOURCE NWM_V3_SHORT_RANGE_06 "
            "--S3_BUCKET b --S3_PREFIX out/ngen.DAILY/short_range/06/VPU_01"]
    out = substitute_daily(cmds, now=NOON)[0]
    assert "-F s3://b/ngen.20260701/forcing_short_range/06/" in out   # -F resolved
    assert "--S3_PREFIX out/ngen.DAILY/short_range/06/VPU_01" in out   # prefix left literal


def test_medium_range_ensemble_hour_shift():
    # member 2 -> 6h shift; init folder 06 -> 00, t06z -> t00z, same date.
    cmds = ["datastream -s DAILY -F s3://b/ngen.DAILY/forcing_medium_range/06/"
            "ngen.t06z.medium_range.forcing.f001_f240.VPU_01.nc "
            "--FORCING_SOURCE NWM_V3_MEDIUM_RANGE_06_2 --S3_PREFIX p/DAILY"]
    out = substitute_daily(cmds, now=NOON)[0]
    assert "/forcing_medium_range/00/ngen.t00z.medium_range" in out
    assert "ngen.20260701" in out


def test_medium_range_shift_rolls_date_back_over_midnight():
    # member 2 (6h) with init folder 00 -> hour 18 the previous day.
    cmds = ["datastream -s DAILY -F s3://b/ngen.DAILY/forcing_medium_range/00/"
            "ngen.t00z.medium_range.forcing.f001_f240.VPU_01.nc "
            "--FORCING_SOURCE NWM_V3_MEDIUM_RANGE_00_2 --S3_PREFIX p/DAILY"]
    out = substitute_daily(cmds, now=NOON)[0]
    assert "/forcing_medium_range/18/ngen.t18z.medium_range" in out
    assert "ngen.20260630" in out   # date rolled back a day


def test_single_member_medium_range_has_no_shift():
    # member 1 -> nhrs_shift 0; the -F path is untouched except DAILY resolution.
    cmds = ["datastream -s DAILY -F s3://b/ngen.DAILY/forcing_medium_range/06/"
            "ngen.t06z.medium_range.forcing.f001_f240.VPU_01.nc "
            "--FORCING_SOURCE NWM_V3_MEDIUM_RANGE_06_1 --S3_PREFIX p/DAILY"]
    out = substitute_daily(cmds, now=NOON)[0]
    assert "/forcing_medium_range/06/ngen.t06z.medium_range" in out


def test_retry_attempt_returns_commands_unchanged():
    # The hour-shift isn't idempotent, so retries must reuse the resolved commands.
    cmds = ["echo DAILY"]
    assert substitute_daily(cmds, now=NOON, retry_attempt=1) == cmds
