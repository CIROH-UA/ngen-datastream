import hashlib
import io
import json
import tarfile
import urllib.error
import zipfile
from datetime import datetime, timezone

import pytest

from research_datastream import contribution_common as common
from research_datastream.contribution_common import Failed

RID = "c128e9bf32df4de587b86d698e1b6831"

SHA = "ab" * 32


def test_check_sha256():
    assert common.check_sha256({}, SHA).status == "pass"
    assert common.check_sha256({"sha256": SHA.upper()}, SHA).status == "pass"
    mismatch = common.check_sha256({"sha256": "cd" * 32}, SHA)
    assert mismatch.status == "fail" and SHA in mismatch.detail
    assert common.check_sha256({"sha256": "abc"}, SHA).status == "fail"
    # Unquoted, an all-digit hash would reach here as an int.
    assert common.check_sha256({"sha256": 12}, SHA).status == "fail"


class Response:
    """Enough of an HTTP response for get()'s callers."""

    def __init__(self, body: bytes, content_type="application/octet-stream"):
        self.body, self.headers = io.BytesIO(body), {"Content-Type": content_type}

    def read(self, n=-1):
        return self.body.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def serve(monkeypatch, handler):
    monkeypatch.setattr(common, "get", lambda url, timeout=60: handler(url))


def test_utc():
    assert common.utc("2026-10-20T20:41:46Z") == datetime(2026, 10, 20, 20, 41, 46, tzinfo=timezone.utc)
    assert common.utc(datetime(2026, 1, 1)).tzinfo == timezone.utc


def test_check_unchanged(monkeypatch):
    spec = {"url": f"https://www.hydroshare.org/resource/{RID}", "last_updated": "2026-10-20T20:41:46Z"}
    assert common.check_unchanged({"url": "https://example.com/x.tar"}).status == "warn"

    serve(monkeypatch, lambda url: Response(json.dumps({"date_last_updated": "2026-10-20T20:41:46Z"}).encode()))
    assert common.check_unchanged(spec).status == "pass"
    serve(monkeypatch, lambda url: Response(json.dumps({"date_last_updated": "2026-10-21T00:00:00Z"}).encode()))
    assert "edited since review" in common.check_unchanged(spec).detail

    def down(url):
        raise urllib.error.URLError("unreachable")
    serve(monkeypatch, down)
    assert common.check_unchanged(spec).status == "fail"


def test_download_hashes_and_caps(monkeypatch, tmp_path):
    body = b"x" * 1000
    serve(monkeypatch, lambda url: Response(body))
    sha, check = common.download("https://example.com/p.tar", tmp_path / "p")
    assert sha == hashlib.sha256(body).hexdigest() and sha in check.detail
    assert (tmp_path / "p").read_bytes() == body

    monkeypatch.setattr(common, "MAX_BYTES", 10)
    with pytest.raises(Failed, match="exceeds"):
        common.download("https://example.com/p.tar", tmp_path / "q")


def test_download_waits_out_the_bag(monkeypatch, tmp_path):
    # The bag's status, then the archive: once to see it is no longer JSON, once to stream it.
    answers = [Response(b'{"bag_status": "in progress"}', "application/json"), Response(b"bag"), Response(b"bag")]
    asked = []
    serve(monkeypatch, lambda url: asked.append(url) or answers.pop(0))
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    sha, _ = common.download(f"https://www.hydroshare.org/resource/{RID}", tmp_path / "p")
    assert sha == hashlib.sha256(b"bag").hexdigest()
    assert asked[0] == f"https://www.hydroshare.org/hsapi/resource/{RID}/"


def tar_of(path, members):
    with tarfile.open(path, "w") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def test_unpack_reaches_into_a_wrapped_archive(tmp_path):
    inner = tar_of(tmp_path / "inner.tar", {"nextgen_VPU_17.gpkg": b"g"})
    outer = tar_of(tmp_path / "outer.tar", {"bag/data/contents/inner.tar": inner.read_bytes()})
    common.unpack(outer, tmp_path / "out")
    assert [p.name for p in (tmp_path / "out").rglob("*.gpkg")] == ["nextgen_VPU_17.gpkg"]


def test_unpack_refuses_unsafe_paths(tmp_path):
    with pytest.raises(Failed, match="Unsafe tar"):
        common.unpack(tar_of(tmp_path / "t.tar", {"../escape": b"x"}), tmp_path / "t")
    with zipfile.ZipFile(tmp_path / "z.zip", "w") as zf:
        zf.writestr("../escape", "x")
    with pytest.raises(Failed, match="Unsafe path"):
        common.unpack(tmp_path / "z.zip", tmp_path / "z")
    (tmp_path / "plain").write_text("neither")
    with pytest.raises(Failed, match="Neither a tar nor a zip"):
        common.unpack(tmp_path / "plain", tmp_path / "p")
    assert not (tmp_path / "escape").exists()
