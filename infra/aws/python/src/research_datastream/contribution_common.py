#!/usr/bin/env python3
"""
Shared machinery for NRDS community contributions.

A contribution names a publicly hosted package, usually a HydroShare resource,
pinned to the version a maintainer reviewed. This module checks the pin,
downloads the package and unpacks it safely. The contribution types build on it.

Author: Jordan Laser
jlaser@lynker.com
"""

from __future__ import annotations

import hashlib
import json
import re
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

BUCKET = "ciroh-community-ngen-datastream"

MAX_BYTES = 2 * 1024**3
BAG_TIMEOUT_S = 600
BAG_POLL_S = 15

USER_AGENT = "nrds-contribution"
ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar", ".tar.bz2", ".tar.xz", ".zip")
IGNORED = {"__MACOSX", ".git"}


def utc(value) -> datetime:
    """A timestamp as an aware UTC datetime. YAML hands back a datetime already."""
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@dataclass
class Check:
    name: str
    status: str  # pass, warn, fail
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status != "fail"

    def __str__(self) -> str:
        icon = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}[self.status]
        return f"[{icon}] {self.name}: {self.detail}"


class Failed(Exception):
    """A check failed hard enough that later ones cannot run."""

    def __init__(self, check: Check):
        self.check = check


def get(url: str, timeout: int = 60):
    request = urllib.request.Request(url)
    request.add_header("User-Agent", USER_AGENT)
    return urllib.request.urlopen(request, timeout=timeout)

# ── the package ─────────────────────────────────────────────────────


def resource_id(url: str) -> Optional[str]:
    match = re.search(r"/resource/([0-9a-fA-F]{32})", url)
    return match.group(1) if match else None


def check_unchanged(spec: dict) -> Check:
    """The resource must still be the version the maintainer pinned."""
    rid = resource_id(spec["url"])
    if not rid:
        return Check(
            "unchanged", "warn", "Not a HydroShare resource; the pin cannot be verified here"
        )
    try:
        with get(f"https://www.hydroshare.org/hsapi/resource/{rid}/sysmeta/", 30) as response:
            live = json.load(response).get("date_last_updated", "")
        same = utc(live) == utc(spec["last_updated"])
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        return Check("unchanged", "fail", f"Could not read the resource metadata: {exc}")

    if same:
        return Check("unchanged", "pass", f"Still the pinned version, {live}")
    return Check(
        "unchanged",
        "fail",
        f"The resource was last updated {live}, not the pinned "
        f"{utc(spec['last_updated']).isoformat()}. "
        "It has been edited since review; re-check it and update the contribution file.",
    )


def download(url: str, dest: Path) -> Tuple[str, Check]:
    """
    Stream the package to disk under a size cap. Returns (sha256, check).

    HydroShare builds a resource bag on demand, answering the first request with
    a JSON status instead of the archive, so the loop waits that out.
    """
    rid = resource_id(url)
    if rid and "/hsapi/" not in url:
        url = f"https://www.hydroshare.org/hsapi/resource/{rid}/"

    waited = 0
    while "/hsapi/" in url:
        with get(url) as response:
            if "json" not in response.headers.get("Content-Type", "").lower():
                break
            status = json.loads(response.read(4096) or b"{}").get("bag_status", "unknown")
        if waited >= BAG_TIMEOUT_S:
            raise Failed(Check("download", "fail", f"HydroShare bag still '{status}' after {waited}s"))
        time.sleep(BAG_POLL_S)
        waited += BAG_POLL_S

    digest = hashlib.sha256()
    total = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with get(url, 120) as response, open(dest, "wb") as handle:
            while chunk := response.read(1 << 18):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise Failed(Check("download", "fail", f"Package exceeds {MAX_BYTES} bytes"))
                digest.update(chunk)
                handle.write(chunk)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise Failed(Check("download", "fail", f"{exc}")) from exc

    return digest.hexdigest(), Check("download", "pass", f"{total} bytes, sha256 {digest.hexdigest()[:16]}...")


def wanted(path: Path) -> bool:
    """False for archiver noise: dotfiles, AppleDouble stubs, __MACOSX."""
    return not path.name.startswith(".") and not any(p in IGNORED for p in path.parts)


def unpack(archive: Path, dest: Path) -> Check:
    """
    Extract the package, then any archive it wraps.

    A HydroShare bag holds the submitted tarball one level down, so a single
    nested pass is needed before the geopackage is visible.
    """
    for target in (archive, None):
        if target is None:
            nested = [
                p for p in sorted(dest.rglob("*"))
                if p.is_file() and wanted(p) and p.name.lower().endswith(ARCHIVE_SUFFIXES)
            ]
            if not nested or any(dest.rglob("*.gpkg")):
                break
            for inner in nested:
                _extract(inner, inner.parent / f"{inner.name}.d")
            break
        _extract(target, dest)

    return Check("unpack", "pass", f"{sum(1 for _ in dest.rglob('*'))} entries")


def _extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tar:
            if sum(m.size for m in tar.getmembers()) > MAX_BYTES:
                raise Failed(Check("unpack", "fail", "Extracted size exceeds cap"))
            try:
                # 'data' rejects absolute paths, traversal, links out of the
                # tree and special files: every guard an untrusted tar needs.
                tar.extractall(dest, filter="data")
            except tarfile.TarError as exc:
                raise Failed(Check("unpack", "fail", f"Unsafe tar: {exc}")) from exc
        return

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            infos = zf.infolist()
            if sum(i.file_size for i in infos) > MAX_BYTES:
                raise Failed(Check("unpack", "fail", "Extracted size exceeds cap"))
            for info in infos:
                name = Path(info.filename)
                if name.is_absolute() or ".." in name.parts:
                    raise Failed(Check("unpack", "fail", f"Unsafe path: {info.filename}"))
            zf.extractall(dest)
        return

    raise Failed(
        Check(
            "unpack",
            "fail",
            "Neither a tar nor a zip. The submission standard is a tarred directory "
            "holding the geopackage and the realization.",
        )
    )
