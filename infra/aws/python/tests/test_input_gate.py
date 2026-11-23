"""Tests for the input gate lambda: DAILY resolved once, then exponential
backoff until the forcing and restart files exist or a day passes."""

import importlib.util
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

GATE = Path(__file__).parents[2] / "terraform/modules/orchestration/lambdas/input_gate/lambda_function.py"
spec = importlib.util.spec_from_file_location("input_gate", GATE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

CMD = ("datastream -s DAILY -F s3://b/ngen.DAILY/forcing_medium_range/00/ngen.t00z.medium_range.forcing.f001_f240.VPU_09.nc "
       "--FORCING_SOURCE NWM_V3_MEDIUM_RANGE_00_2 -t s3://b/restarts/ngen.DAILY/00/channel_restart_DAILY_000000.nc "
       "--S3_BUCKET b --S3_PREFIX out/ngen.DAILY/medium_range/00/2/VPU_09")


class FakeS3:
    def __init__(self, present=(), code="404"):
        self.present, self.code, self.heads = set(present), code, []

    def head_object(self, Bucket, Key):
        self.heads.append(f"s3://{Bucket}/{Key}")
        if self.heads[-1] not in self.present:
            raise ClientError({"Error": {"Code": self.code}}, "HeadObject")


@pytest.fixture
def clock(monkeypatch):
    t = {"now": 1_000_000.0}
    monkeypatch.setattr(gate.time, "time", lambda: t["now"])
    return t


def run(event, s3, monkeypatch):
    monkeypatch.setattr(gate.boto3, "client", lambda *a, **k: s3)
    return gate.lambda_handler(event, None)


def test_waits_with_backoff_then_passes(clock, monkeypatch):
    s3 = FakeS3()
    ev = run({"commands": [CMD], "run_options": {}, "retry_attempt": 0}, s3, monkeypatch)
    resolved = ev["commands"][0]
    assert "DAILY" not in resolved.replace("-s DAILY", "")
    assert "/forcing_medium_range/18/" in resolved   # member 2 hour shift applied once
    assert len(ev["missing_inputs"]) == 2 and not ev["ii_inputs_ready"] and not ev["ii_inputs_timed_out"]
    waits = [ev["input_wait_s"]]
    for _ in range(5):
        clock["now"] += ev["input_wait_s"]
        ev = run(ev, s3, monkeypatch)
        waits.append(ev["input_wait_s"])
    assert ev["commands"][0] == resolved              # not re-resolved on later checks
    assert waits == [60, 120, 240, 480, 900, 900]
    s3.present = set(s3.heads)
    ev = run(ev, s3, monkeypatch)
    assert ev["ii_inputs_ready"] and ev["missing_inputs"] == []


def test_times_out_after_a_day(clock, monkeypatch):
    s3 = FakeS3()
    ev = run({"commands": [CMD], "run_options": {}}, s3, monkeypatch)
    n = 0
    while not ev["ii_inputs_timed_out"]:
        clock["now"] += ev["input_wait_s"]
        ev = run(ev, s3, monkeypatch)
        n += 1
    assert clock["now"] - 1_000_000.0 == 86400        # last wait clamped to the deadline
    assert not ev["ii_inputs_ready"] and n < 120


def test_no_dynamic_inputs_passes_immediately(clock, monkeypatch):
    s3 = FakeS3()
    ev = run({"commands": ["python fp.py --S3_BUCKET b --S3_PREFIX p/DAILY"], "run_options": {}}, s3, monkeypatch)
    assert ev["ii_inputs_ready"] and s3.heads == []


def test_opt_out_skips_check(clock, monkeypatch):
    s3 = FakeS3()
    ev = run({"commands": [CMD], "run_options": {"ii_wait_for_inputs": False}}, s3, monkeypatch)
    assert ev["ii_inputs_ready"] and s3.heads == []


def test_access_denied_raises(clock, monkeypatch):
    with pytest.raises(ClientError):
        run({"commands": [CMD], "run_options": {}}, FakeS3(code="403"), monkeypatch)
