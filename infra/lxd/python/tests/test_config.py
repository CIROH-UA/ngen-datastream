"""Tests for the datastream YAML loader and cron rendering (config.py).

Exercises the real datastream definitions under terraform/datastreams so the
run fan-out (init x vpu x member), instance-type sizing, and cron formulas stay
in sync with the shipped configs. VPU sets are read back from the loaded config
rather than hardcoded, so these don't become yet another copy of the list.
"""

from pathlib import Path

from research_datastream_lxd.config import _cron, load_all, load_datastream

DATASTREAMS = Path(__file__).resolve().parents[2] / "terraform" / "datastreams"


# ---- cron rendering ----------------------------------------------------

def test_cron_simple_hour():
    assert _cron("{init} % 24", "0", 6) == "0 6 * * *"


def test_cron_hour_wraps_midnight():
    # cfe-nom short_range: (init + 1) % 24; init 23 -> hour 0
    assert _cron("({init} + 1) % 24", "0", 23) == "0 0 * * *"


def test_cron_member_minute_offset():
    # medium_range minute stagger: floor(((member - 1) * (1/7) * 60) % 60)
    expr = "floor((({member} - 1) * (1.0 / 7.0) * 60) % 60)"
    assert _cron("({init} + 3) % 24", expr, 0, member=1) == "0 3 * * *"
    assert _cron("({init} + 3) % 24", expr, 0, member=2) == "8 3 * * *"


# ---- forcing (one run per init) ----------------------------------------

def test_forcing_run_count():
    ds = load_datastream(DATASTREAMS / "forcing")
    # 24 short_range + 4 medium_range + 1 analysis_assim_extend
    assert len(ds.runs) == 29
    assert all(r.vpu is None for r in ds.runs)   # forcing splits VPUs inside one command


# ---- cfe-nom (fans out one run per init x vpu [x member]) --------------

def test_cfe_nom_fans_out_per_vpu():
    ds = load_datastream(DATASTREAMS / "cfe-nom")
    sr = [r for r in ds.runs if r.group == "short_range"]
    n_vpus = len({r.vpu for r in sr})
    # 24 inits x n_vpus short_range + 4 inits x n_vpus medium_range + 1 x n_vpus AnA
    assert len(sr) == 24 * n_vpus
    assert len(ds.runs) == (24 + 4 + 1) * n_vpus


def test_cfe_nom_vpu_sets_match_across_groups():
    # All three schedule groups must cover the same VPUs, or a VPU would silently
    # run in one forecast configuration but not another.
    ds = load_datastream(DATASTREAMS / "cfe-nom")
    by_group = {}
    for r in ds.runs:
        by_group.setdefault(r.group, set()).add(r.vpu)
    sets = list(by_group.values())
    assert all(s == sets[0] for s in sets)


def test_cfe_nom_instance_type_sizing():
    ds = load_datastream(DATASTREAMS / "cfe-nom")
    # VPU 10U short_range is m8g.4xlarge -> 16 cpu / 64GiB; nprocs = cpu - 1
    run = next(r for r in ds.runs if r.group == "short_range" and r.vpu == "10U")
    assert run.resources["cpu"] == 16
    assert run.resources["memory"] == "64GiB"
    assert run.context["nprocs"] == 15


def test_run_name_and_cron_encode_fanout():
    ds = load_datastream(DATASTREAMS / "cfe-nom")
    run = next(r for r in ds.runs
               if r.group == "medium_range" and r.vpu == "01" and r.init == "06")
    assert run.name == "cfe-nom_medium_range_init06_vpu01_mem1"
    assert run.cron == "0 9 * * *"        # (6 + 3) % 24 = 9, minute 0
    assert run.member == "1"


# ---- discovery ---------------------------------------------------------

def test_load_all_discovers_both_datastreams():
    assert {d.name for d in load_all(DATASTREAMS)} == {"forcing", "cfe-nom"}
