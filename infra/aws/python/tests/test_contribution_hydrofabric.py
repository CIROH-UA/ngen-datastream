import sqlite3

import pytest

from research_datastream import contribution_hydrofabric as hf
from research_datastream.contribution_common import Failed
from research_datastream.vpu_resources import resources


def gpkg(path, vpu="17", nexus=("nex-1", "nex-2"), extra_layer=False):
    """A geopackage with just enough of the hydrofabric's layers for the checks."""
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE gpkg_contents (table_name TEXT);
        CREATE TABLE divides (fid INTEGER, divide_id TEXT, toid TEXT, vpuid TEXT, geom BLOB);
        CREATE TABLE flowpaths (fid INTEGER, id TEXT, toid TEXT, divide_id TEXT);
        CREATE TABLE nexus (fid INTEGER, id TEXT, toid TEXT);
        INSERT INTO gpkg_contents VALUES ('divides'), ('flowpaths'), ('nexus');
        """
    )
    db.executemany("INSERT INTO divides VALUES (?, ?, ?, ?, ?)",
                   [(1, "cat-1", "wb-1", vpu, b"a"), (2, "cat-2", "wb-2", vpu, b"b")])
    db.executemany("INSERT INTO flowpaths VALUES (?, ?, ?, ?)",
                   [(1, "wb-1", nexus[0], "cat-1"), (2, "wb-2", nexus[1], "cat-2")])
    db.executemany("INSERT INTO nexus VALUES (?, ?, ?)", [(1, nexus[0], "wb-2"), (2, nexus[1], None)])
    if extra_layer:
        db.execute("CREATE TABLE lakes (fid INTEGER, id TEXT)")
        db.execute("INSERT INTO gpkg_contents VALUES ('lakes')")
    db.commit()
    db.close()
    return path


def attached(cand, live):
    db = sqlite3.connect(cand)
    db.execute("ATTACH DATABASE ? AS live", (str(live),))
    return db


def test_load(tmp_path):
    f = tmp_path / "423.yml"
    f.write_text('issue: 423\nurl: https://x\nlast_updated: 2026-10-19T16:30:00Z\nvpus: ["17", "03W"]\n')
    spec = hf.load(f)
    assert spec["vpus"] == ["03W", "17"]
    f.write_text("issue: 423\nurl: https://x\nlast_updated: 2026-10-19T16:30:00Z\nvpus: [9]\n")
    with pytest.raises(Failed, match="quote them"):
        hf.load(f)


def test_find_geopackages_bare_and_mismatch(tmp_path):
    archive = gpkg(tmp_path / "upload.bin")
    found, check = hf.find_geopackages(archive, tmp_path / "x", ["17"])
    assert list(found) == ["17"] and check.ok
    with pytest.raises(Failed, match="lists 16"):
        hf.find_geopackages(archive, tmp_path / "y", ["16"])


def test_checks_against_live(tmp_path):
    live = gpkg(tmp_path / "live.gpkg")
    cand = gpkg(tmp_path / "cand.gpkg", nexus=("nex-1", "nex-3"), extra_layer=True)
    db = attached(cand, live)
    c, l = hf.layers(db, "main"), hf.layers(db, "live")
    assert hf.check_layers(c, l).status == "warn"
    assert hf.check_ids(db, c, l).status == "pass"
    changes = hf.diff(db, c, l)
    assert changes["nexus_added"] == 1 and changes["nexus_removed"] == 1
    assert any("nwm_to_ngen_map" in s for s in hf.impacts(changes, "17"))
    with pytest.raises(Failed, match="layers"):
        hf.check_layers(l | {"lakes": ["fid", "id"]}, c | {"extra": ["id"]})


def test_identical_sees_what_diff_does_not_count(tmp_path):
    live = gpkg(tmp_path / "live.gpkg")
    cand = gpkg(tmp_path / "cand.gpkg")
    db = attached(cand, live)
    c, l = hf.layers(db, "main"), hf.layers(db, "live")
    assert hf.identical(db, c, l)
    # A divides column diff() does not examine.
    db.execute("UPDATE main.divides SET vpuid = '16' WHERE divide_id = 'cat-1'")
    assert not any(hf.diff(db, c, l).values())
    assert not hf.identical(db, c, l)
    # The same rows, one repeated in place of another.
    db.execute("UPDATE main.divides SET vpuid = '17'")
    db.execute("UPDATE main.nexus SET id = 'nex-1', toid = 'wb-2' WHERE fid = 2")
    db.execute("INSERT INTO live.nexus VALUES (3, 'nex-2', NULL)")
    db.execute("INSERT INTO main.nexus VALUES (3, 'nex-2', NULL)")
    assert not hf.identical(db, c, l)
    db.close()


def test_malformed_nexus_id_fails(tmp_path):
    live = gpkg(tmp_path / "live.gpkg")
    cand = gpkg(tmp_path / "cand.gpkg", nexus=("nex-1", "nex-3e+06"))
    db = attached(cand, live)
    with pytest.raises(Failed, match="nex-3e"):
        hf.check_ids(db, hf.layers(db, "main"), hf.layers(db, "live"))


def test_paths_and_overrides():
    spec = {"issue": 423, "vpus": ["17"]}
    p = hf.paths(spec)
    assert p["geopackage_prefix"] == "resources/v2.2_hydrofabric/geopackages/contributions/423"
    assert p["bmi_prefixes"]["cfe-nom"] == "resources/v2.2_hydrofabric/bmi_configs/cfe_nom/contributions/423"
    text = hf.overrides(spec)
    assert 'geopackage  = "resources/v2.2_hydrofabric/geopackages/contributions/423/nextgen_VPU_17.gpkg"' in text
    assert "bmi_configs/lstm_0/contributions/423/VPU_17/ngen-bmi-configs.tar.gz" in text
    routing = text.split("datastreams/routing-only/main.tf")[1]
    assert "bmi_configs" not in routing


MAIN_TF = """
locals {
  vpu_resource_overrides = {%s}
  vpu_resources = {
    for vpu in var.all_vpus : vpu => merge({
      geopackage = "resources/geopackages/VPU_${vpu}/nextgen_VPU_${vpu}.gpkg"
    }, try(local.vpu_resource_overrides[vpu], {}))
  }
}
"""


def with_main_tf(monkeypatch, overrides):
    """live_key reading a fixed main.tf per datastream, not the repository's."""
    texts = {ds: MAIN_TF % overrides.get(ds, "") for ds in hf.GEOPACKAGE_DATASTREAMS}
    monkeypatch.setattr(hf, "resources", lambda ds, vpu: resources(ds, vpu, texts[ds]))


def test_live_key_when_the_datastreams_agree(monkeypatch):
    with_main_tf(monkeypatch, {})
    assert hf.live_key("17") == ("resources/geopackages/VPU_17/nextgen_VPU_17.gpkg", None)


def test_live_key_warns_when_one_is_overridden(monkeypatch):
    with_main_tf(monkeypatch, {"lstm_0": '"17" = { geopackage = "contributions/423/nextgen_VPU_17.gpkg" }'})
    key, warning = hf.live_key("17")
    assert key == "resources/geopackages/VPU_17/nextgen_VPU_17.gpkg"
    assert warning.status == "warn" and "lstm_0 runs contributions/423/nextgen_VPU_17.gpkg" in warning.detail


class FakeS3:
    def __init__(self, heads):
        self.heads = heads

    def head_object(self, Bucket, Key):
        from botocore.exceptions import ClientError

        head = self.heads[Key]
        if isinstance(head, str):
            raise ClientError({"Error": {"Code": head}}, "HeadObject")
        return head


def test_existing_sha256_tells_absent_from_unknown():
    s3 = FakeS3({"gone": "404", "bare": {"Metadata": {}}, "known": {"Metadata": {"sha256": "ab"}},
                 "denied": "403"})
    assert hf.existing_sha256(s3, "gone") == (False, None)
    assert hf.existing_sha256(s3, "bare") == (True, None)
    assert hf.existing_sha256(s3, "known") == (True, "ab")
    from botocore.exceptions import ClientError
    with pytest.raises(ClientError):
        hf.existing_sha256(s3, "denied")
