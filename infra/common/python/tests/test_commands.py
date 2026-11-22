"""Tests for the shared DAILY-token resolution logic (research_datastream_core).

Both orchestrators call this, so these lock in what production AWS has always
done: the forecast-cycle fold-back, the MEDIUM_RANGE ensemble hour-shift, and
dating `--S3_PREFIX` for ngen runs at launch rather than in datastreamcli.
"""

from datetime import datetime, timezone

import pytest

from research_datastream_core import (
    daily_fcst_cycle,
    extract_forcing_file,
    extract_forcing_source,
    extract_restart_file,
    extract_s3_bucket,
    extract_s3_prefix,
    resolve_daily_date,
    resolve_offset_tokens,
    run_init,
    substitute_daily,
)

UTC = timezone.utc
NOON = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


# ---- extraction --------------------------------------------------------

def test_extract_last_match_wins():
    assert extract_s3_prefix(["--s3_prefix a/first", "--s3_prefix b/second"]) == "b/second"


def test_extract_s3_bucket_case_insensitive():
    assert extract_s3_bucket(["--S3_BUCKET my-bucket --S3_PREFIX p"]) == "my-bucket"
    assert extract_s3_bucket(["no bucket here"]) is None


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


def test_ngen_run_dates_prefix_and_forcing_file():
    cmds = ["datastream -s DAILY -F s3://b/ngen.DAILY/forcing_short_range/06/"
            "ngen.t06z.short_range.forcing.f001_f018.VPU_01.nc "
            "--FORCING_SOURCE NWM_V3_SHORT_RANGE_06 "
            "--S3_BUCKET b --S3_PREFIX out/ngen.DAILY/short_range/06/VPU_01"]
    out = substitute_daily(cmds, now=NOON)[0]
    assert "-F s3://b/ngen.20260701/forcing_short_range/06/" in out
    assert "--S3_PREFIX out/ngen.20260701/short_range/06/VPU_01" in out
    assert "-s DAILY" in out   # datastreamcli resolves its own start date


def test_production_cfe_nom_command():
    # Shape of the AWS cfe-nom template; the expected prefix matches the
    # execution.json production wrote for ngen.20261019/short_range/06/VPU_01.
    cmds = ["runuser -l ec2-user -c '/home/ec2-user/datastreamcli/scripts/datastream "
            "-s DAILY -n 3 -F s3://bkt/forcings/v2.2_hydrofabric/ngen.DAILY/forcing_short_range/06/"
            "ngen.t06z.short_range.forcing.f001_f018.VPU_01.nc --FORCING_SOURCE NWM_V3_SHORT_RANGE_06 "
            "-t s3://bkt/restarts/v2.2_hydrofabric/ngen.DAILY/06/channel_restart_DAILY_060000.nc "
            "--S3_BUCKET bkt --S3_PREFIX outputs/cfe_nom/v2.2_hydrofabric/ngen.DAILY/short_range/06/VPU_01'"]
    out = substitute_daily(cmds, now=datetime(2026, 10, 19, 7, 5, tzinfo=UTC))[0]
    assert "--S3_PREFIX outputs/cfe_nom/v2.2_hydrofabric/ngen.20261019/short_range/06/VPU_01'" in out
    assert "/ngen.20261019/forcing_short_range/06/" in out
    assert "-t s3://bkt/restarts/v2.2_hydrofabric/ngen.20261019/06/channel_restart_20261019_060000.nc " in out
    assert out.count("DAILY") == 1   # only -s DAILY, left for datastreamcli


AAE_CMD = ("datastream -s DAILY -F s3://b/ngen.DAILY/forcing_analysis_assim_extend/{init}/"
           "ngen.t{init}z.analysis_assim_extend.forcing.tm27_tm00.VPU_09.nc "
           "--FORCING_SOURCE NWM_V3_ANALYSIS_ASSIM_EXTEND_{init} "
           "-t s3://b/restarts/ngen.{{DAILY-28h:YYYYMMDD}}/{{DAILY-28h:HH}}/"
           "channel_restart_{{DAILY-28h:YYYYMMDD}}_{{DAILY-28h:HH}}0000.nc "
           "--S3_BUCKET b --S3_PREFIX out/ngen.DAILY/analysis_assim_extend/{init}/VPU_09")


def test_analysis_assim_extend_restart_is_init_minus_28h():
    # 16z init on 11/22 simulates from 11/21 13z; t-route starts from 11/21 12z.
    out = substitute_daily([AAE_CMD.format(init="16")], now=datetime(2026, 11, 22, 19, 0, tzinfo=UTC))[0]
    assert "-t s3://b/restarts/ngen.20261121/12/channel_restart_20261121_120000.nc " in out
    assert "--S3_PREFIX out/ngen.20261122/analysis_assim_extend/16/VPU_09" in out


def test_analysis_assim_extend_restart_follows_fold_back():
    # Before the 16z cycle the run folds back to 11/21, so the restart is 11/20.
    out = substitute_daily([AAE_CMD.format(init="16")], now=datetime(2026, 11, 22, 3, 0, tzinfo=UTC))[0]
    assert "ngen.20261120/12/channel_restart_20261120_120000.nc" in out


def test_offset_token_crosses_midnight():
    # A 02z init minus 28h lands two days back, at 22z.
    init = datetime(2026, 11, 22, 2, tzinfo=UTC)
    assert resolve_offset_tokens("{DAILY-28h:YYYYMMDD}/{DAILY-28h:HH}", init) == "20261120/22"
    assert resolve_offset_tokens("{DAILY:YYYYMMDD}{DAILY:HH} {DAILY+6h:HH}", init) == "2026112202 08"


def test_offset_token_without_forcing_source():
    # The standalone-DAILY pass must not reach inside the token; no source folds back to 06/30 00z.
    cmds = ["run --S3_PREFIX p/DAILY -t s3://b/{DAILY-24h:YYYYMMDD}/r.nc"]
    assert substitute_daily(cmds, now=NOON) == ["run --S3_PREFIX p/20260630 -t s3://b/20260629/r.nc"]


def test_run_init_and_restart_extraction():
    assert run_init("20261122", "NWM_V3_SHORT_RANGE_06") == datetime(2026, 11, 22, 6, tzinfo=UTC)
    assert run_init("20261122", "NWM_V3_MEDIUM_RANGE_12_3") == datetime(2026, 11, 22, 12, tzinfo=UTC)
    assert extract_restart_file(["datastream -t s3://b/r.nc -w s3://b/x.nc --troute_x y"]) == "s3://b/r.nc"


def test_medium_range_shift_keeps_prefix_on_run_date():
    # The ensemble shift moves the forcing file to yesterday 18z; the output
    # prefix stays on the run's date.
    cmds = ["datastream -s DAILY -F s3://b/ngen.DAILY/forcing_medium_range/00/"
            "ngen.t00z.medium_range.forcing.f001_f240.VPU_01.nc "
            "--FORCING_SOURCE NWM_V3_MEDIUM_RANGE_00_2 --S3_BUCKET b --S3_PREFIX p/ngen.DAILY/00/2"]
    out = substitute_daily(cmds, now=NOON)[0]
    assert "-F s3://b/ngen.20260630/forcing_medium_range/18/" in out
    assert "--S3_PREFIX p/ngen.20260701/00/2" in out


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
