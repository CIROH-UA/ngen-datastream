#!/usr/bin/env python3
"""
Validate and deploy an NRDS community hydrofabric contribution: one or more
whole-VPU geopackages.

    python -m research_datastream.contribution_hydrofabric check  <contribution.yml> [--vpu 17]
    python -m research_datastream.contribution_hydrofabric deploy --stage <directory>
    python -m research_datastream.contribution_hydrofabric paths  <contribution.yml>
    python -m research_datastream.contribution_hydrofabric overrides <contribution.yml>

Each candidate is compared against the geopackage the NRDS currently runs for
its VPU, as the datastreams' main.tf name it. Structural problems fail the
check. The differences decide which of the resources derived from the
geopackage, beyond the BMI configurations rebuilt with it, would need
regenerating.

Deploying never overwrites. Each geopackage, and the BMI configurations built
from it, is written under the contribution's issue number. Nothing runs them
until a VPU's entry in vpu_resource_overrides points at them; `overrides`
prints those entries.

`check` runs on public reads alone. Only `deploy` needs AWS credentials. The
contribution file format is documented in
infra/aws/terraform/services/nrds/hydrofabric/contributions/README.md.

Author: Jordan Laser
jlaser@lynker.com
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from research_datastream.contribution_common import (
    BUCKET,
    Check,
    Failed,
    check_unchanged,
    download,
    get,
    unpack,
    utc,
    wanted,
)
from research_datastream.vpu_resources import resources

RESOURCES = "resources/v2.2_hydrofabric"
GEOPACKAGES = RESOURCES + "/geopackages/contributions/{issue}"
BMI_CONFIGS = RESOURCES + "/bmi_configs/{set}/contributions/{issue}"

# The datastreams that read a VPU geopackage, and those of them built from BMI configurations.
GEOPACKAGE_DATASTREAMS = ("cfe-nom", "lstm_0", "routing-only")
BMI_DATASTREAMS = ("cfe-nom", "lstm_0")

VPUS = {
    "01", "02", "03N", "03S", "03W", "04", "05", "06", "07", "08", "09",
    "10L", "10U", "11", "12", "13", "14", "15", "16", "17", "18",
}

REQUIRED_KEYS = ("issue", "url", "last_updated", "vpus")

# Columns holding hydrofabric identifiers, which must be <prefix>-<integer>.
ID_COLUMNS = ("id", "toid", "divide_id", "link", "to")
ID_FORMAT = re.compile(r"^[a-z]+-\d+$")

SQLITE_MAGIC = b"SQLite format 3\x00"


def public_url(key: str) -> str:
    return f"https://{BUCKET}.s3.amazonaws.com/{key}"


def normalize_vpu(value) -> str:
    """YAML reads an unquoted 01 as the integer 1."""
    vpu = str(value).upper()
    return vpu.zfill(2) if vpu.isdigit() else vpu.zfill(3)


# ── where a contribution is deployed ────────────────────────────────


def geopackage_key(issue: int, vpu: str) -> str:
    return f"{GEOPACKAGES.format(issue=issue)}/nextgen_VPU_{vpu}.gpkg"


def bmi_prefix(datastream: str, issue: int) -> str:
    return BMI_CONFIGS.format(set=datastream.replace("-", "_"), issue=issue)


def bmi_key(datastream: str, issue: int, vpu: str) -> str:
    return f"{bmi_prefix(datastream, issue)}/VPU_{vpu}/ngen-bmi-configs.tar.gz"


def paths(spec: dict) -> dict:
    """What the workflow needs to place, build and test a contribution."""
    return {
        "issue": spec["issue"],
        "vpus": spec["vpus"],
        "geopackage_prefix": GEOPACKAGES.format(issue=spec["issue"]),
        "bmi_prefixes": {ds: bmi_prefix(ds, spec["issue"]) for ds in BMI_DATASTREAMS},
        "geopackage_datastreams": list(GEOPACKAGE_DATASTREAMS),
        "bmi_datastreams": list(BMI_DATASTREAMS),
    }


def overrides(spec: dict) -> str:
    """The vpu_resource_overrides entries that point each datastream at the contribution."""
    lines = []
    for ds in GEOPACKAGE_DATASTREAMS:
        lines += [f"datastreams/{ds}/main.tf", ""]
        for vpu in spec["vpus"]:
            entry = {"geopackage": geopackage_key(spec["issue"], vpu)}
            if ds in BMI_DATASTREAMS:
                entry["bmi_configs"] = bmi_key(ds, spec["issue"], vpu)
            width = max(len(k) for k in entry)
            lines.append(f'    "{vpu}" = {{')
            lines += [f'      {k.ljust(width)} = "{v}"' for k, v in entry.items()]
            lines.append("    }")
        lines.append("")
    return "\n".join(lines)


# ── the contribution file ───────────────────────────────────────────


def load(path: Path) -> dict:
    spec = yaml.safe_load(path.read_text()) or {}
    missing = [key for key in REQUIRED_KEYS if not spec.get(key)]
    if missing:
        raise Failed(Check("contribution_file", "fail", f"Missing: {', '.join(missing)}"))

    vpus = spec["vpus"] if isinstance(spec["vpus"], list) else [spec["vpus"]]
    unknown = [str(v) for v in vpus if not isinstance(v, str) or v not in VPUS]
    if unknown:
        raise Failed(
            Check("contribution_file", "fail", f"Unknown VPU(s) {', '.join(unknown)}; quote them, e.g. \"09\"")
        )
    if len(set(vpus)) != len(vpus):
        raise Failed(Check("contribution_file", "fail", "A VPU is listed more than once"))
    if not isinstance(spec["issue"], int):
        raise Failed(Check("contribution_file", "fail", "issue must be a number"))
    spec["vpus"] = sorted(vpus)
    try:
        spec["last_updated"] = utc(spec["last_updated"])
    except ValueError as exc:
        raise Failed(Check("contribution_file", "fail", f"last_updated: {exc}")) from exc
    return spec


# ── the package ─────────────────────────────────────────────────────


def gpkg_vpu(gpkg: Path) -> List[str]:
    try:
        db = sqlite3.connect(f"file:{gpkg}?mode=ro", uri=True)
        found = sorted({str(r[0]) for r in db.execute("SELECT DISTINCT vpuid FROM divides") if r[0]})
        db.close()
    except sqlite3.Error as exc:
        raise Failed(Check("contents", "fail", f"{gpkg.name}: cannot read divides.vpuid: {exc}")) from exc
    return found


def find_geopackages(archive: Path, root: Path, expected: List[str]) -> Tuple[Dict[str, Path], Check]:
    """
    {vpu: geopackage} for every geopackage in the package, which may itself
    be a single geopackage. Each must hold one whole VPU, no VPU may appear
    twice, and together they must be exactly the VPUs the contribution lists.
    """
    with open(archive, "rb") as handle:
        bare = handle.read(len(SQLITE_MAGIC)) == SQLITE_MAGIC
    if bare:
        root.mkdir(parents=True, exist_ok=True)
        packages = [root / "candidate.gpkg"]
        shutil.copyfile(archive, packages[0])
    else:
        unpack(archive, root)
        packages = [p for p in sorted(root.rglob("*.gpkg")) if p.is_file() and wanted(p)]
    if not packages:
        raise Failed(Check("contents", "fail", "No .gpkg found in the package"))

    by_vpu: Dict[str, Path] = {}
    for gpkg in packages:
        found = gpkg_vpu(gpkg)
        if len(found) != 1:
            raise Failed(
                Check(
                    "contents",
                    "fail",
                    f"{gpkg.name} holds divides from VPU(s) {', '.join(found) or 'none'}. "
                    "Each geopackage must be one whole VPU.",
                )
            )
        vpu = normalize_vpu(found[0])
        if vpu in by_vpu:
            raise Failed(
                Check("contents", "fail", f"VPU {vpu} appears in both {by_vpu[vpu].name} and {gpkg.name}")
            )
        by_vpu[vpu] = gpkg

    if sorted(by_vpu) != expected:
        raise Failed(
            Check(
                "contents",
                "fail",
                f"The package holds VPU(s) {', '.join(sorted(by_vpu))}, the contribution "
                f"file lists {', '.join(expected)}",
            )
        )
    return by_vpu, Check("contents", "pass", ", ".join(f"VPU {v}: {p.name}" for v, p in by_vpu.items()))


# ── what production runs ────────────────────────────────────────────


def live_key(vpu: str) -> Tuple[str, Optional[Check]]:
    """
    The geopackage production runs for a VPU. The datastreams normally agree;
    when one has been pointed elsewhere the first is compared against, with a warning.
    """
    found = {ds: resources(ds, vpu)["geopackage"] for ds in GEOPACKAGE_DATASTREAMS}
    key = found[GEOPACKAGE_DATASTREAMS[0]]
    others = {ds: k for ds, k in found.items() if k != key}
    if not others:
        return key, None
    detail = f"Compared with {GEOPACKAGE_DATASTREAMS[0]}'s {key}; " + ", ".join(
        f"{ds} runs {k}" for ds, k in others.items()
    )
    return key, Check(f"live[{vpu}]", "warn", detail)


def fetch_live(vpu: str, dest: Path) -> Tuple[Path, str, List[Check]]:
    key, warning = live_key(vpu)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with get(public_url(key), 120) as response, open(dest, "wb") as handle:
        shutil.copyfileobj(response, handle, 1 << 20)
    return dest, key, [warning or Check(f"live[{vpu}]", "pass", key)]


# ── the geopackage ──────────────────────────────────────────────────


def q(name: str) -> str:
    """Quote an identifier. Several hydrofabric layers have hyphens in their names."""
    return '"' + name.replace('"', '""') + '"'


def layers(db: sqlite3.Connection, schema: str) -> Dict[str, List[str]]:
    """{layer: [columns]} for every layer the geopackage registers."""
    names = [r[0] for r in db.execute(f"SELECT table_name FROM {schema}.gpkg_contents")]
    return {
        name: [r[1] for r in db.execute(f"PRAGMA {schema}.table_info({q(name)})")]
        for name in names
    }


def check_integrity(db: sqlite3.Connection) -> Check:
    result = db.execute("PRAGMA main.quick_check").fetchone()[0]
    if result != "ok":
        raise Failed(Check("integrity", "fail", result))
    return Check("integrity", "pass", "SQLite quick_check ok")


def check_layers(cand: Dict[str, List[str]], live: Dict[str, List[str]]) -> Check:
    """Every layer and column the NRDS copy has. Extra ones are allowed."""
    missing_layers = sorted(set(live) - set(cand))
    missing_columns = {
        name: sorted(set(cols) - set(cand[name]))
        for name, cols in live.items()
        if name in cand and set(cols) - set(cand[name])
    }
    if missing_layers or missing_columns:
        detail = []
        if missing_layers:
            detail.append("missing layers: " + ", ".join(missing_layers))
        for name, cols in missing_columns.items():
            detail.append(f"{name} is missing {', '.join(cols)}")
        raise Failed(Check("layers", "fail", "; ".join(detail)))

    extra = sorted(set(cand) - set(live))
    if extra:
        return Check("layers", "warn", f"Layers the NRDS copy does not have: {', '.join(extra)}")
    return Check("layers", "pass", f"All {len(live)} layers and their columns present")


def malformed_ids(db: sqlite3.Connection, schema: str, tables: Dict[str, List[str]]) -> set:
    """(layer, column, value) for every identifier not of the form prefix-integer."""
    bad = set()
    for name, cols in tables.items():
        for col in cols:
            if col not in ID_COLUMNS:
                continue
            rows = db.execute(
                f"SELECT DISTINCT {q(col)} FROM {schema}.{q(name)} "
                f"WHERE {q(col)} IS NOT NULL AND typeof({q(col)}) = 'text'"
            )
            bad.update((name, col, r[0]) for r in rows if not ID_FORMAT.match(r[0]))
    return bad


def check_ids(db, cand: Dict[str, List[str]], live: Dict[str, List[str]]) -> Check:
    """
    New malformed identifiers fail. So does any malformed nexus identifier,
    since t-route parses those as integers (issue #199). Others that the NRDS
    copy already carries are reported but not held against the contribution.
    """
    found = malformed_ids(db, "main", cand)
    inherited = malformed_ids(db, "live", live)
    blocking = sorted(v for v in found if v not in inherited or v[2].startswith("nex-"))
    if blocking:
        sample = ", ".join(f"{name}.{col}={val}" for name, col, val in blocking[:5])
        raise Failed(
            Check("ids", "fail", f"{len(blocking)} malformed identifier(s), e.g. {sample}")
        )
    if found:
        values = ", ".join(sorted({v[2] for v in found})[:5])
        return Check("ids", "warn", f"Malformed identifiers inherited from the NRDS copy: {values}")
    return Check("ids", "pass", "Every identifier is prefix-integer")


TOPOLOGY = {
    "flowpaths whose toid is not a nexus": (
        "SELECT count(*) FROM {s}.flowpaths WHERE toid IS NOT NULL "
        "AND toid NOT IN (SELECT id FROM {s}.nexus)"
    ),
    "nexuses whose toid is not a flowpath": (
        "SELECT count(*) FROM {s}.nexus WHERE toid IS NOT NULL "
        "AND toid NOT IN (SELECT id FROM {s}.flowpaths)"
    ),
    "flowpaths whose divide is missing": (
        "SELECT count(*) FROM {s}.flowpaths WHERE divide_id IS NOT NULL "
        "AND divide_id NOT IN (SELECT divide_id FROM {s}.divides)"
    ),
}


def check_topology(db: sqlite3.Connection) -> Check:
    """Dangling references, compared with what the NRDS copy already has."""
    worse = []
    for label, sql in TOPOLOGY.items():
        cand = db.execute(sql.format(s="main")).fetchone()[0]
        live = db.execute(sql.format(s="live")).fetchone()[0]
        if cand > live:
            worse.append(f"{label}: {cand} (NRDS copy {live})")
    if worse:
        return Check("topology", "warn", "; ".join(worse))
    return Check("topology", "pass", "No more dangling references than the NRDS copy")


# ── what changed, and what that implies ─────────────────────────────


def count(db: sqlite3.Connection, sql: str) -> int:
    return db.execute(sql).fetchone()[0]


def id_changes(db: sqlite3.Connection, table: str, key: str) -> Tuple[int, int]:
    """(added, removed) values of key between the NRDS copy and the candidate."""
    t, k = q(table), q(key)
    added = count(db, f"SELECT count(*) FROM main.{t} WHERE {k} NOT IN (SELECT {k} FROM live.{t})")
    removed = count(db, f"SELECT count(*) FROM live.{t} WHERE {k} NOT IN (SELECT {k} FROM main.{t})")
    return added, removed


def changed_rows(db, table: str, key: str, cand: Dict[str, List[str]], live: Dict[str, List[str]],
                 only: Optional[List[str]] = None) -> int:
    """
    Candidate rows, over the key and the shared columns (or `only` these), with
    no identical row in the NRDS copy. Compared as sets rather than joined on
    the key, because some layers repeat keys and EXCEPT treats NULLs as equal.
    """
    cols = [c for c in cand[table] if c in live[table] and c not in ("fid", key)]
    if only is not None:
        cols = [c for c in cols if c in only]
    if not cols:
        return 0
    select = ", ".join(q(c) for c in [key, *cols])
    t = q(table)
    return count(
        db, f"SELECT count(*) FROM (SELECT {select} FROM main.{t} EXCEPT SELECT {select} FROM live.{t})"
    )


def diff(db, cand: Dict[str, List[str]], live: Dict[str, List[str]]) -> Dict[str, int]:
    changes = {}
    for table, key in (("divides", "divide_id"), ("flowpaths", "id"), ("nexus", "id")):
        changes[f"{table}_added"], changes[f"{table}_removed"] = id_changes(db, table, key)
    changes["divides_geometry"] = changed_rows(db, "divides", "divide_id", cand, live, ["geom"])
    changes["divides_toid"] = changed_rows(db, "divides", "divide_id", cand, live, ["toid"])
    changes["flowpaths_toid"] = changed_rows(db, "flowpaths", "id", cand, live, ["toid"])
    changes["nexus_toid"] = changed_rows(db, "nexus", "id", cand, live, ["toid"])
    for table in ("divide-attributes", "flowpath-attributes"):
        key = "divide_id" if table.startswith("divide") else "id"
        changes[table] = changed_rows(db, table, key, cand, live) if table in live else 0
    return changes


def impacts(changes: Dict[str, int], vpu: str) -> List[str]:
    """The derived resources a deployment leaves stale. BMI configurations are rebuilt with it."""
    divides_set = changes["divides_added"] or changes["divides_removed"]
    stale = ["`conus_nextgen.gpkg`, if qkrig should see the change"]
    if divides_set or changes["divides_geometry"]:
        stale.append(
            f"Forcing weights: `weights/nextgen_VPU_{vpu}_weights.json` and the copy baked into the AMI"
        )
    if divides_set:
        stale.append("t-route restart catchment map `troute_restart/hf2.2_ref_hf_catchment_map.json`")
    if changes["nexus_added"] or changes["nexus_removed"]:
        stale.append("Routing-only nexus map `mappings/nwm_to_ngen_map.json`")
    if changes["flowpaths_added"] or changes["flowpaths_removed"] or changes["flowpaths_toid"]:
        stale.append("t-route restart crosswalk `troute_restart/crosswalk.nc` (verify)")
    return stale


# ── running it ──────────────────────────────────────────────────────


def check_vpu(vpu: str, gpkg: Path, workdir: Path) -> dict:
    """Every check of one candidate against the geopackage production runs for its VPU."""
    result = {"vpu": vpu, "geopackage": str(gpkg), "checks": [], "changes": {}, "stale": []}
    checks = result["checks"]
    live_path = workdir / f"live_VPU_{vpu}.gpkg"
    try:
        live_path, result["live_key"], found = fetch_live(vpu, live_path)
        checks.extend(found)
        db = sqlite3.connect(f"file:{gpkg}?mode=ro", uri=True)
        db.execute("ATTACH DATABASE ? AS live", (f"file:{live_path}?mode=ro",))
        try:
            checks.append(check_integrity(db))
            cand, live = layers(db, "main"), layers(db, "live")
            checks.append(check_layers(cand, live))
            checks.append(check_ids(db, cand, live))
            checks.append(check_topology(db))
            result["changes"] = diff(db, cand, live)
        finally:
            db.close()
        if not any(result["changes"].values()):
            raise Failed(Check("diff", "fail", "The candidate is identical to the geopackage in production"))
        result["stale"] = impacts(result["changes"], vpu)
        checks.append(Check("diff", "pass", ", ".join(f"{k}={v}" for k, v in result["changes"].items() if v)))
    except Failed as failure:
        checks.append(failure.check)
    finally:
        live_path.unlink(missing_ok=True)
    result["passed"] = all(c.ok for c in checks)
    return result


def build(spec: dict, workdir: Path, only: Optional[str] = None) -> Tuple[List[Check], List[dict], str]:
    """The package-level checks, then every candidate's own. Returns (checks, per-VPU results, sha)."""
    checks = [check_unchanged(spec)]
    if not checks[0].ok:
        raise Failed(checks[0])
    archive = workdir / "package.bin"
    sha, check = download(spec["url"], archive)
    checks.append(check)
    candidates, check = find_geopackages(archive, workdir / "extracted", spec["vpus"])
    checks.append(check)
    archive.unlink()

    vpus = [only] if only else spec["vpus"]
    if only and only not in candidates:
        raise Failed(Check("contents", "fail", f"VPU {only} is not in this contribution"))
    return checks, [check_vpu(v, candidates[v], workdir) for v in vpus], sha


def report(spec: dict, checks: List[Check], results: List[dict]) -> str:
    lines = [f"### Hydrofabric contribution #{spec['issue']}: VPU {', '.join(spec['vpus'])}", ""]
    if checks:
        lines += ["| Package check | Result | Detail |", "|---|---|---|"]
        lines += [f"| {c.name} | {c.status.upper()} | {c.detail.replace('|', '/')} |" for c in checks]
    for result in results:
        lines += ["", f"#### VPU {result['vpu']}", "", "| Check | Result | Detail |", "|---|---|---|"]
        lines += [
            f"| {c.name} | {c.status.upper()} | {c.detail.replace('|', '/')} |" for c in result["checks"]
        ]
        changed = {k: v for k, v in result["changes"].items() if v}
        if changed:
            lines += ["", "Differences from production: " + ", ".join(f"{k} {v}" for k, v in changed.items())]
        if result["stale"]:
            lines += ["", "Deploying leaves these stale until they are regenerated:", ""]
            lines += [f"- {item}" for item in result["stale"]]
    return "\n".join(lines) + "\n"


def serializable(result: dict) -> dict:
    return {**result, "checks": [str(c) for c in result["checks"]]}


def cmd_check(args) -> int:
    spec = load(Path(args.contribution))
    only = normalize_vpu(args.vpu) if args.vpu else None
    checks, results, sha = [], [], ""
    try:
        checks, results, sha = build(spec, Path(args.workdir), only)
    except Failed as failure:
        checks.append(failure.check)

    for check in checks:
        print(check)
    for result in results:
        for check in result["checks"]:
            print(f"VPU {result['vpu']} {check}")
    if args.report:
        Path(args.report).write_text(report(spec, checks, results))
    if args.record:
        Path(args.record).write_text(
            json.dumps(
                {
                    **spec,
                    "last_updated": utc(spec["last_updated"]).isoformat(),
                    "package_sha256": sha,
                    "results": [serializable(r) for r in results],
                },
                indent=2,
            )
            + "\n"
        )
    passed = bool(results) and all(c.ok for c in checks) and all(r["passed"] for r in results)
    return 0 if passed else 1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def cmd_deploy(args) -> int:
    """
    Upload a staged contribution's geopackages under its issue, from the
    record a passing `check` wrote, laid out as

        <stage>/record.json
        <stage>/geopackages/nextgen_VPU_XX.gpkg

    A key already holding the same file is left as it is, so a rerun
    resumes; one holding a different file fails.
    """
    stage = Path(args.stage)
    record = json.loads((stage / "record.json").read_text())
    if not record["results"] or not all(r["passed"] for r in record["results"]):
        print(Check("deploy", "fail", "The staged record is of a contribution that did not pass"))
        return 1

    uploads = [
        (stage / f"geopackages/nextgen_VPU_{r['vpu']}.gpkg", geopackage_key(record["issue"], r["vpu"]))
        for r in record["results"]
    ]
    missing = [str(path) for path, _ in uploads if not path.is_file()]
    if missing:
        print(Check("deploy", "fail", f"Not staged: {', '.join(missing)}"))
        return 1
    if args.dry_run:
        for path, key in uploads:
            print(Check("deploy", "pass", f"Would write {path} to s3://{BUCKET}/{key}"))
        return 0

    import boto3
    from botocore.exceptions import ClientError

    s3 = boto3.client("s3")
    for path, key in uploads:
        digest = sha256(path)
        try:
            existing = s3.head_object(Bucket=BUCKET, Key=key)["Metadata"].get("sha256")
        except ClientError:
            existing = None
        if existing == digest:
            print(Check("deploy", "pass", f"s3://{BUCKET}/{key} already holds it"))
            continue
        if existing is not None:
            print(Check("deploy", "fail", f"s3://{BUCKET}/{key} holds a different file"))
            return 1
        s3.upload_file(
            str(path), BUCKET, key,
            ExtraArgs={"ContentType": "application/geopackage+sqlite3", "Metadata": {"sha256": digest}},
        )
        if s3.head_object(Bucket=BUCKET, Key=key)["Metadata"].get("sha256") != digest:
            print(Check("deploy", "fail", f"s3://{BUCKET}/{key} did not land intact"))
            return 1
        print(Check("deploy", "pass", f"s3://{BUCKET}/{key} @ {digest[:16]}..."))
    return 0


def cmd_paths(args) -> int:
    print(json.dumps(paths(load(Path(args.contribution)))))
    return 0


def cmd_overrides(args) -> int:
    print(overrides(load(Path(args.contribution))), end="")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="research_datastream.contribution_hydrofabric")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Validate the candidates against production")
    check.add_argument("contribution")
    check.add_argument("--vpu", default="", help="Check only this VPU's geopackage")
    check.add_argument("--workdir", default="./contribution-work")
    check.add_argument("--record", default="", help="Write the resolved contribution here")
    check.add_argument("--report", default="", help="Write a markdown report here")
    check.set_defaults(func=cmd_check)

    deploy = sub.add_parser("deploy", help="Upload checked geopackages under the contribution's issue")
    deploy.add_argument("--stage", required=True, help="Directory holding record.json and geopackages/")
    deploy.add_argument("--dry-run", action="store_true")
    deploy.set_defaults(func=cmd_deploy)

    where = sub.add_parser("paths", help="Print, as JSON, where the contribution is placed and built")
    where.add_argument("contribution")
    where.set_defaults(func=cmd_paths)

    entries = sub.add_parser("overrides", help="Print the vpu_resource_overrides entries that deploy it")
    entries.add_argument("contribution")
    entries.set_defaults(func=cmd_overrides)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Failed as failure:
        print(failure.check)
        return 1


if __name__ == "__main__":
    sys.exit(main())
