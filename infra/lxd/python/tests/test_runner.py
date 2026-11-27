"""Tests for the run's DAILY resolution and output check (runner.py), driven by
the real cfe-nom and forcing templates so the S3 key checked is the one the run
actually writes."""

from datetime import datetime, timezone
from pathlib import Path

from research_datastream_core import substitute_daily
from research_datastream_lxd import runner
from research_datastream_lxd.config import load_datastream

DATASTREAMS = Path(__file__).resolve().parents[2] / "terraform" / "datastreams"
NOW = datetime(2026, 10, 19, 7, 5, tzinfo=timezone.utc)
ENV = {"s3_bucket": "bkt", "ds_tag": "1", "ngiab_tag": "1"}


class FakeS3:
    def __init__(self):
        self.listed = []

    def list_objects_v2(self, Bucket, Prefix):
        self.listed.append((Bucket, Prefix))
        return {"Contents": [{"Key": Prefix}]}


def _checked_key(datastream, group, init, vpu=None):
    ds = load_datastream(DATASTREAMS / datastream, env=ENV)
    rs = next(r for r in ds.runs if r.group == group and r.init == init and r.vpu == vpu)
    execution = runner._render_template(rs.template_path, rs.context)
    execution["commands"] = substitute_daily(execution["commands"], now=NOW)
    check = runner.S3OutputCheck.__new__(runner.S3OutputCheck)
    check._s3 = FakeS3()
    assert check.verify(execution)
    return check._s3.listed[0]


def test_cfe_nom_checks_dated_merkdir():
    bucket, key = _checked_key("cfe-nom", "short_range", "06", vpu="01")
    assert bucket == "bkt"
    assert "DAILY" not in key
    assert key.endswith("/ngen.20261019/short_range/06/VPU_01/merkdir.file")


def test_forcing_checks_metadata_csv():
    _, key = _checked_key("forcing", "short_range", "06")
    assert "DAILY" not in key
    assert key.endswith("/metadata/forcings_metadata/metadata.csv")
