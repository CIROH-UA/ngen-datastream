import json

import pytest

from research_datastream.vpu_test import load_overrides, module_addresses, override, pick, rewrite

CMD = (
    "runuser -l ec2-user -c 'export DS_TAG=1.7.1 && /home/ec2-user/datastreamcli/scripts/datastream "
    "-s DAILY -n 3 -F s3://bkt/forcings/v2.2_hydrofabric/ngen.DAILY/forcing_short_range/{init}/"
    "ngen.t{init}z.short_range.forcing.f001_f018.VPU_{vpu}.nc --FORCING_SOURCE NWM_V3_SHORT_RANGE_{init} "
    "-N s3://bkt/bmi/VPU_{vpu}/ngen-bmi-configs.tar.gz -g s3://bkt/gpkg/nextgen_VPU_{vpu}.gpkg "
    "--S3_BUCKET bkt --S3_PREFIX outputs/cfe_nom/v2.2_hydrofabric/ngen.DAILY/short_range/{init}/VPU_{vpu}'"
)


def schedule(init, vpu):
    execution = {
        "commands": [CMD.format(init=init, vpu=vpu)],
        "run_options": {"timeout_s": 3600},
        "instance_parameters": {
            "TagSpecifications": [{"ResourceType": "instance", "Tags": [
                {"Key": "Name", "Value": f"prod_VPU{vpu}"},
                {"Key": "Project", "Value": "datastream_FULLCONUS"},
            ]}],
        },
    }
    target = {"StateMachineArn": "arn:sm", "Name": "n", "Input": json.dumps(execution)}
    return {"name": f"short_range_fcst{init}_vpu{vpu}_schedule_cfe_nom_prod",
            "target": [{"input": json.dumps(target)}]}


def test_rewrite_pins_date_and_moves_output():
    ex = json.loads(json.loads(schedule("05", "16")["target"][0]["input"])["Input"])
    cmd = rewrite(ex, "20261015", "test/cicd/vpu-test/1")["commands"][0]
    assert "-s DAILY -e 202610150000" in cmd
    assert "ngen.20261015/forcing_short_range/05/" in cmd
    assert "--S3_PREFIX test/cicd/vpu-test/1/outputs/cfe_nom/v2.2_hydrofabric/ngen.20261015/" in cmd
    assert cmd.count("DAILY") == 1


def test_rewrite_retags_and_leaves_input_alone():
    ex = json.loads(json.loads(schedule("00", "01")["target"][0]["input"])["Input"])
    out = rewrite(ex, "20261015", "t")
    tags = {t["Key"]: t["Value"] for t in out["instance_parameters"]["TagSpecifications"][0]["Tags"]}
    assert tags == {"Name": "vputest_prod_VPU01", "Project": "nrds_vpu_test"}
    assert "--S3_PREFIX outputs/" in ex["commands"][0]


def test_pick_init_00_per_run_type_and_vpu():
    scheds = [schedule(i, v) for i in ("12", "00", "06") for v in ("01", "10L")]
    picked = pick(scheds, ["short_range"], None)
    assert list(picked) == [("short_range", "01"), ("short_range", "10L")]
    assert picked[("short_range", "10L")]["schedule"] == "short_range_fcst00_vpu10L_schedule_cfe_nom_prod"
    assert list(pick(scheds, ["short_range"], ["10L"])) == [("short_range", "10L")]
    assert pick(scheds, ["medium_range"], None) == {}


def test_pick_falls_back_to_earliest_init():
    picked = pick([schedule("16", "01"), schedule("18", "01")], ["short_range"], None)
    assert picked[("short_range", "01")]["schedule"].startswith("short_range_fcst16_")


def test_module_addresses(tmp_path):
    tf = tmp_path / "main.tf"
    tf.write_text('module "cfe_nom_schedules" {\n  source = "./datastreams/cfe-nom"\n}\n'
                  'module "nrds_orchestration" {\n  source = "../../modules/orchestration"\n}\n')
    assert module_addresses(tf) == {"cfe-nom": "module.cfe_nom_schedules"}


def execution(vpu="17"):
    return json.loads(json.loads(schedule("00", vpu)["target"][0]["input"])["Input"])


def test_override_replaces_matching_flags_only(tmp_path):
    f = tmp_path / "o.txt"
    f.write_text("# candidate\n* -g 17 s3://t/nextgen_VPU_17.gpkg\ncfe-nom -N 17 s3://t/cfe.tar.gz\n"
                 "lstm_0 -N 17 s3://t/lstm.tar.gz\n* -g 16 s3://t/16.gpkg\n")
    ex = execution("17")
    applied = override(ex, "cfe-nom", "17", load_overrides(f))
    cmd = ex["commands"][0]
    assert applied == ["-g s3://t/nextgen_VPU_17.gpkg", "-N s3://t/cfe.tar.gz"]
    assert "-g s3://t/nextgen_VPU_17.gpkg " in cmd and "-N s3://t/cfe.tar.gz " in cmd
    assert "lstm" not in cmd and "16.gpkg" not in cmd
    assert "-F s3://bkt/forcings" in cmd


def test_override_after_rewrite_keeps_value_verbatim(tmp_path):
    ex = rewrite(execution("17"), "20261015", "t")
    override(ex, "cfe-nom", "17", [("*", "-g", "*", "s3://t/DAILY/nextgen_VPU_17.gpkg")])
    assert "-g s3://t/DAILY/nextgen_VPU_17.gpkg " in ex["commands"][0]


def test_override_wildcard_skips_absent_flag_named_one_fails():
    ex = execution("17")
    assert override(ex, "routing-only", "17", [("*", "-R", "17", "x")]) == []
    with pytest.raises(SystemExit):
        override(ex, "cfe-nom", "17", [("cfe-nom", "-R", "17", "x")])


def test_load_overrides_rejects_malformed(tmp_path):
    f = tmp_path / "o.txt"
    f.write_text("cfe-nom 17 s3://x\n")
    with pytest.raises(SystemExit):
        load_overrides(f)
