import io
import json
from types import SimpleNamespace

import pytest

from research_datastream import regenerate_missing as rm

BUCKET = "ciroh-community-ngen-datastream"
ARN = "arn:aws:states:us-east-1:000000000000:stateMachine:nrds_prod_sm"


def cfe_template(init="23", vpu="01"):
    return {
        "commands": [
            "runuser -l ec2-user -c 'export DS_TAG=1.7.1 && /home/ec2-user/datastreamcli/scripts/datastream "
            f"-s DAILY -n 3 -F s3://{BUCKET}/forcings/v2.2_hydrofabric/ngen.DAILY/forcing_short_range/{init}/"
            f"ngen.t{init}z.short_range.forcing.f001_f018.VPU_{vpu}.nc --FORCING_SOURCE NWM_V3_SHORT_RANGE_{init} "
            f"--S3_BUCKET {BUCKET} --S3_PREFIX outputs/cfe_nom/v2.2_hydrofabric/ngen.DAILY/short_range/{init}/VPU_{vpu}'"
        ],
        "run_options": {"ii_check_s3": True, "n_retries_allowed": 2},
        "instance_parameters": {"ImageId": "ami-1", "InstanceType": "m8g.xlarge"},
    }


def forcing_template(init="23"):
    return {
        "commands": [
            "runuser -l ec2-user -c 'docker run x configure_datastream.py --start_date DAILY "
            f"--forcing_source NWM_V3_SHORT_RANGE_{init} --s3_bucket {BUCKET} "
            f"--s3_prefix forcings/v2.2_hydrofabric/ngen.DAILY/forcing_short_range/{init}'"
        ],
        "run_options": {"ii_check_s3": True, "n_retries_allowed": 2},
        "instance_parameters": {"ImageId": "ami-2", "InstanceType": "m8g.2xlarge"},
    }


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class NoSuchKey(Exception):
    pass


class FakeS3:
    exceptions = SimpleNamespace(NoSuchKey=NoSuchKey)

    def __init__(self, objects):
        self.objects = objects  # key -> bytes

    def list_objects_v2(self, Bucket, Prefix, MaxKeys=1000):
        keys = sorted(k for k in self.objects if k.startswith(Prefix))[:MaxKeys]
        return {"Contents": [{"Key": k} for k in keys]} if keys else {}

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise NoSuchKey(Key)
        return {"Body": io.BytesIO(self.objects[Key])}


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self, **_):
        return self.pages


class FakeScheduler:
    def __init__(self, schedules):
        self.schedules = schedules  # name -> execution

    def get_paginator(self, _):
        return FakePaginator([{"Schedules": [{"Name": n} for n in self.schedules]}])

    def get_schedule(self, Name, GroupName):
        target = {"StateMachineArn": ARN, "Name": "x", "Input": json.dumps(self.schedules[Name])}
        return {"Target": {"Input": json.dumps(target)}}


class FakeSFN:
    def __init__(self, running=()):
        self.running = running
        self.started = []

    def get_paginator(self, _):
        return FakePaginator([{"executions": [{"name": n} for n in self.running]}])

    def start_execution(self, stateMachineArn, name, input):
        self.started.append((name, json.loads(input)))
        return {"executionArn": f"{stateMachineArn}:{name}"}


def args(**kw):
    base = dict(
        start="20260823", end="", datastreams=None, run_types=None, init_cycles=None, members=None,
        vpus=None, source="execution", environment="prod", schedule_group="default",
        state_machine_arn="", min_age_hours=12, tag="t", workers=2,
    )
    base.update(kw)
    return SimpleNamespace(**base)


# --------------------------------------------------------------------------- #
# Units
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "name, expected",
    [
        ("short_range_fcst23_vpu01_schedule_cfe_nom_prod", ("cfe_nom", "short_range", "23", "", "01")),
        ("medium_range_fcst06_mem1_vpu10L_schedule_lstm_0_prod", ("lstm_0", "medium_range", "06", "1", "10L")),
        ("analysis_assim_extend_fcst16_vpu03W_schedule_cfe_nom_prod",
         ("cfe_nom", "analysis_assim_extend", "16", "", "03W")),
        ("short_range_fcst05_forcing_schedule_prod", ("forcing", "short_range", "05", "", "")),
        ("restart_init05_schedule_prod", ("restart", "", "05", "", "")),
    ],
)
def test_parse_schedule_name(name, expected):
    sim = rm.parse_schedule_name(name, "prod")
    assert (sim.datastream, sim.run_type, sim.init, sim.member, sim.vpu) == expected


@pytest.mark.parametrize(
    "name",
    [
        "short_range_fcst23_vpu01_schedule_nwm_routing_test_nwm_routing",
        "nrds-weekly-stats-schedule",
        "qkrig_init00_schedule_prod",
    ],
)
def test_parse_schedule_name_skips(name):
    assert rm.parse_schedule_name(name, "prod") is None


def test_resolve_date_pins_daily():
    out = rm.resolve_date(cfe_template(), "20260823")
    cmd = out["commands"][0]
    assert "DAILY" not in cmd.replace("-s DAILY", "")
    assert "-s DAILY -e 202608230000 " in cmd
    assert f"ngen.20260823/forcing_short_range/23/" in cmd
    assert "--S3_PREFIX outputs/cfe_nom/v2.2_hydrofabric/ngen.20260823/short_range/23/VPU_01'" in cmd


def test_resolve_date_keeps_existing_end():
    ex = {"commands": ["datastream -s DAILY -e 202601010000 --S3_PREFIX a/ngen.DAILY/b"]}
    assert rm.resolve_date(ex, "20260823")["commands"][0] == (
        "datastream -s DAILY -e 202601010000 --S3_PREFIX a/ngen.20260823/b"
    )


def test_resolve_date_tokens_inside_words():
    ex = {"commands": ["-t s3://b/ngen.DAILY/23/channel_restart_DAILY_230000.nc DATE=DAILY qkrig_output_DAILY.parquet"]}
    assert rm.resolve_date(ex, "20260823")["commands"][0] == (
        "-t s3://b/ngen.20260823/23/channel_restart_20260823_230000.nc DATE=20260823 qkrig_output_20260823.parquet"
    )


def test_resolve_date_pins_restart_clock():
    # the restart template picks its date from the instance clock
    ex = {"commands": [
        "DATE=$(date -u +%Y%m%d) && INIT=05 && if [ $INIT -gt $(date -u +%H) ]; then "
        "DATE=$(date -u -d yesterday +%Y%m%d); fi && echo $DATE > /home/ec2-user/run/run_date.txt",
        "runuser -l ec2-user -c 'echo \"END: $(date -u +%Y%m%d%H%M%S)\"'",
    ]}
    cmds = rm.resolve_date(ex, "20260801")["commands"]
    assert cmds[0] == (
        "DATE=20260801 && INIT=05 && if [ $INIT -gt 23 ]; then "
        "DATE=20260731; fi && echo $DATE > /home/ec2-user/run/run_date.txt"
    )
    assert "$(date -u +%Y%m%d%H%M%S)" in cmds[1]


def test_resolve_date_pins_analysis_restart_date():
    ex = {"commands": ["runuser -l ec2-user -c 'RESTART_DATE=$(date -u -d yesterday +%Y%m%d) && "
                       "datastream -s DAILY -t s3://b/restarts/ngen.${RESTART_DATE}/12/x.nc'"]}
    assert "RESTART_DATE=20260822 &&" in rm.resolve_date(ex, "20260823")["commands"][0]


def test_resolve_date_refuses_unknown_clock():
    ex = {"commands": ["D=$(date -u -d '2 days ago' +%Y%m%d)"]}
    with pytest.raises(ValueError, match="reads the clock"):
        rm.resolve_date(ex, "20260823")


def test_clean_strips_run_state():
    stored = cfe_template()
    stored["instance_parameters"].update(InstanceId="i-1", MaxCount=1, MinCount=1, InstanceMarketOptions={})
    stored.update(t0=1.0, ii_s3_object_checked=False, retry_attempt=2, region="us-east-1", volume_id="v",
                  command_id="c", failedInput={}, wait_seconds=3600, ii_pass=False)
    assert rm.clean(stored) == cfe_template()


def test_location_and_execution_key():
    ex = rm.resolve_date(cfe_template(), "20260823")
    bucket, prefix = rm.location(ex)
    assert bucket == BUCKET
    assert rm.execution_key(prefix).endswith("VPU_01/datastream-metadata/execution.json")
    _, fprefix = rm.location(rm.resolve_date(forcing_template(), "20260823"))
    assert rm.execution_key(fprefix).endswith("forcing_short_range/23/metadata/execution.json")


def test_is_complete_markers():
    ex = rm.resolve_date(cfe_template(), "20260823")
    _, prefix = rm.location(ex)
    assert not rm.is_complete(FakeS3({f"{prefix}/datastream-metadata/execution.json": b""}), ex, BUCKET, prefix)
    assert rm.is_complete(FakeS3({f"{prefix}/merkdir.file": b""}), ex, BUCKET, prefix)

    fx = rm.resolve_date(forcing_template(), "20260823")
    _, fprefix = rm.location(fx)
    # restart writes this with a doubled slash
    assert rm.is_complete(FakeS3({f"{fprefix}/metadata/forcings_metadata//metadata.csv": b""}), fx, BUCKET, fprefix)
    assert rm.is_complete(FakeS3({f"{fprefix}/metadata/forcings_metadata/metadata.csv/a.csv": b""}), fx, BUCKET, fprefix)
    assert not rm.is_complete(FakeS3({f"{fprefix}/metadata/execution.json": b""}), fx, BUCKET, fprefix)


def test_execution_name_fits_step_functions():
    sim = rm.Simulation("routing_only", "analysis_assim_extend", "16", "1", "10L", "s")
    job = rm.Job(sim=sim, date="20260823", template={}, state_machine_arn=ARN)
    name = rm.execution_name(job, "20261015T120000")
    assert len(name) <= 80 and rm.name_stem(name) + "_20261015T120000" == name


def test_select_filters_only_their_dimension():
    sims = [
        rm.parse_schedule_name(n, "prod")
        for n in (
            "short_range_fcst23_vpu01_schedule_cfe_nom_prod",
            "short_range_fcst23_vpu02_schedule_cfe_nom_prod",
            "short_range_fcst23_forcing_schedule_prod",
            "medium_range_fcst00_mem1_vpu01_schedule_cfe_nom_prod",
        )
    ]
    picked = rm.select(sims, {"datastream": None, "run_type": {"short_range"}, "init": None,
                              "member": {"1"}, "vpu": {"01"}})
    assert [s.schedule for s in picked] == [
        "short_range_fcst23_vpu01_schedule_cfe_nom_prod",
        "short_range_fcst23_forcing_schedule_prod",
    ]


# --------------------------------------------------------------------------- #
# Planning against fakes
# --------------------------------------------------------------------------- #
def world(stored_forcing=True, forcing_done=False):
    schedules = {
        "short_range_fcst23_vpu01_schedule_cfe_nom_prod": cfe_template("23", "01"),
        "short_range_fcst22_vpu01_schedule_cfe_nom_prod": cfe_template("22", "01"),
        "short_range_fcst23_forcing_schedule_prod": forcing_template("23"),
    }
    d = "20260823"
    cfe23 = f"outputs/cfe_nom/v2.2_hydrofabric/ngen.{d}/short_range/23/VPU_01"
    cfe22 = f"outputs/cfe_nom/v2.2_hydrofabric/ngen.{d}/short_range/22/VPU_01"
    f23 = f"forcings/v2.2_hydrofabric/ngen.{d}/forcing_short_range/23"
    failed = rm.resolve_date(cfe_template("23", "01"), d)
    failed["commands"][0] = failed["commands"][0].replace("-n 3", "-n 7")  # tell stored from schedule
    failed["instance_parameters"]["InstanceId"] = "i-1"
    failed.update(t0=1.0, retry_attempt=2)
    objects = {
        f"{cfe22}/merkdir.file": b"",
        f"forcings/v2.2_hydrofabric/ngen.{d}/forcing_short_range/22/ngen.t22z.short_range.forcing.f001_f018.VPU_01.nc": b"",
        f"{cfe23}/datastream-metadata/execution.json": json.dumps(failed).encode(),
    }
    if stored_forcing:
        objects[f"{f23}/metadata/execution.json"] = json.dumps(rm.resolve_date(forcing_template(), d)).encode()
    if forcing_done:
        objects[f"{f23}/metadata/forcings_metadata/metadata.csv"] = b""
        objects[f"{f23}/ngen.t23z.short_range.forcing.f001_f018.VPU_01.nc"] = b""
    return FakeScheduler(schedules), FakeS3(objects)


def by_label(jobs):
    return {(j.sim.datastream, j.sim.init): j for j in jobs}


def test_plan_regenerates_from_stored_execution_and_its_input():
    scheduler, s3 = world()
    jobs = by_label(rm.plan(args(), scheduler, s3, FakeSFN()))
    assert jobs[("cfe_nom", "22")].status == "complete"
    cfe, forcing = jobs[("cfe_nom", "23")], jobs[("forcing", "23")]
    assert (cfe.status, cfe.source) == ("missing", "stored execution")
    assert "-n 7" in cfe.execution["commands"][0]
    assert "InstanceId" not in cfe.execution["instance_parameters"] and "t0" not in cfe.execution
    assert forcing.status == "missing"


def test_plan_does_not_check_inputs():
    # the cfe run's forcing is missing and not being regenerated; send it anyway
    scheduler, s3 = world()
    jobs = by_label(rm.plan(args(datastreams={"cfe_nom"}), scheduler, s3, FakeSFN()))
    assert jobs[("cfe_nom", "23")].status == "missing"


def test_plan_schedule_source_and_skips():
    scheduler, s3 = world(forcing_done=True)
    jobs = by_label(rm.plan(args(source="schedule"), scheduler, s3, FakeSFN()))
    cfe = jobs[("cfe_nom", "23")]
    assert (cfe.status, cfe.source) == ("missing", "schedule")
    assert cfe.execution == rm.resolve_date(cfe_template("23", "01"), "20260823")
    assert jobs[("forcing", "23")].status == "complete"

    running = FakeSFN(running=["regen_cfe_nom_short_range_20260823_i23_v01_earlier"])
    jobs = by_label(rm.plan(args(), scheduler, s3, running))
    assert jobs[("cfe_nom", "23")].detail == "already being regenerated"

    jobs = rm.plan(args(start="21000101"), scheduler, s3, FakeSFN())
    assert {j.status for j in jobs} == {"skipped"}


def test_main_submits(monkeypatch, tmp_path):
    scheduler, s3 = world()
    sfn = FakeSFN()
    clients = {"scheduler": scheduler, "s3": s3, "stepfunctions": sfn}
    fake_boto3 = SimpleNamespace(
        Session=lambda region_name: SimpleNamespace(client=lambda name: clients[name])
    )
    monkeypatch.setitem(__import__("sys").modules, "boto3", fake_boto3)

    assert rm.main(["--start", "20260823", "--out", str(tmp_path), "--interval", "0", "--tag", "t"]) == 0
    assert sorted(n for n, _ in sfn.started) == [
        "regen_cfe_nom_short_range_20260823_i23_v01_t",
        "regen_forcing_short_range_20260823_i23_t",
    ]
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert sorted(e["status"] for e in manifest) == ["complete", "submitted", "submitted"]
    assert (tmp_path / "executions" / "regen_forcing_short_range_20260823_i23_t.json").exists()

    sfn.started.clear()
    assert rm.main(["--start", "20260823", "--out", str(tmp_path), "--max-executions", "1"]) == 2
    assert sfn.started == []
