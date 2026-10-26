#!/usr/bin/env python3
"""
Validate and deploy an NRDS community parameter contribution.

    python -m research_datastream.contribution_parameters check  <contribution.yml> --out cand.json
    python -m research_datastream.contribution_parameters deploy <contribution.yml>

A contribution is one YAML file committed beside the datastream it changes;
the README in that directory documents the fields.

`check` runs on public reads alone. Only `deploy` needs AWS credentials.

Author: Jordan Laser
jlaser@lynker.com
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
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

REALIZATION = "realizations/{datastream}/realization_VPU_{vpu}.json"
ARCHIVE = "realizations/{datastream}/archive/VPU_{vpu}/{stamp}.{commit}.json"
PROVENANCE = "parameters/{datastream}/{issue}.json"

# VPUs each datastream runs. cfe_nom omits 17, per issue #199.
DATASTREAM_VPUS = {
    "cfe_nom": {
        "01", "02", "03N", "03S", "03W", "04", "05", "06", "07", "08", "09",
        "10L", "10U", "11", "12", "13", "14", "15", "16", "18",
    }
}

REQUIRED_KEYS = ("issue", "url", "last_updated", "type")
TYPES = ("lumped", "per_catchment")


# ── the contribution file ───────────────────────────────────────────


def load(path: Path) -> dict:
    """Read a contribution file. The datastream is the directory it sits in."""
    spec = yaml.safe_load(path.read_text()) or {}
    missing = [key for key in REQUIRED_KEYS if not spec.get(key)]
    if missing:
        raise Failed(Check("contribution_file", "fail", f"Missing: {', '.join(missing)}"))
    if spec["type"] not in TYPES:
        raise Failed(
            Check("contribution_file", "fail", f"type must be one of {', '.join(TYPES)}")
        )

    # .../datastreams/<datastream>/contributions/<issue>.yml. The terraform
    # directory is hyphenated; every S3 prefix uses underscores.
    spec["datastream"] = path.resolve().parent.parent.name.replace("-", "_")
    if spec["datastream"] not in DATASTREAM_VPUS:
        raise Failed(Check("contribution_file", "fail", f"Unknown datastream {spec['datastream']}"))
    try:
        spec["last_updated"] = utc(spec["last_updated"])
    except ValueError as exc:
        raise Failed(Check("contribution_file", "fail", f"last_updated: {exc}")) from exc
    return spec


def find_files(root: Path, subdir: Optional[str]) -> Tuple[Path, Path, Check]:
    """
    Locate the geopackage and the realization beside it.

    Matched on extension rather than name, since filenames vary in practice.
    """
    packages = [p for p in sorted(root.rglob("*.gpkg")) if p.is_file() and wanted(p)]
    if subdir:
        packages = [p for p in packages if p.parent.name == subdir]
    if not packages:
        where = f" under {subdir}/" if subdir else ""
        raise Failed(Check("contents", "fail", f"No .gpkg found{where}"))
    if len(packages) > 1:
        raise Failed(
            Check(
                "contents",
                "fail",
                "More than one .gpkg: " + ", ".join(str(p.relative_to(root)) for p in packages)
                + ". Set `subdir` to the gage directory this contribution covers.",
            )
        )

    gpkg = packages[0]
    realizations = [p for p in sorted(gpkg.parent.glob("*.json")) if p.is_file() and wanted(p)]
    if len(realizations) != 1:
        raise Failed(
            Check(
                "contents",
                "fail",
                f"Expected exactly one .json beside {gpkg.name}, found {len(realizations)}",
            )
        )
    return gpkg, realizations[0], Check("contents", "pass", f"{gpkg.name} and {realizations[0].name}")


def divides(gpkg: Path, datastream: str) -> Tuple[List[str], str, Check]:
    """Read the divide ids and their VPU. A GeoPackage is a SQLite database."""
    try:
        connection = sqlite3.connect(f"file:{gpkg}?mode=ro", uri=True)
        rows = connection.execute("SELECT divide_id, vpuid FROM divides").fetchall()
    except sqlite3.Error as exc:
        raise Failed(
            Check(
                "divides",
                "fail",
                f"Could not read divide_id and vpuid from 'divides': {exc}. Re-subset "
                "from the v2.2 hydrofabric so both are carried through.",
            )
        ) from exc

    ids = sorted({str(row[0]) for row in rows})
    vpus = sorted({str(row[1]) for row in rows if row[1]})
    if not ids:
        raise Failed(Check("divides", "fail", "'divides' is empty"))
    if len(vpus) != 1:
        raise Failed(
            Check(
                "divides",
                "fail",
                f"The divides span {', '.join(vpus) or 'no'} VPU(s). Each contribution "
                "updates one VPU's realization, so split this into one file per VPU.",
            )
        )
    if vpus[0] not in DATASTREAM_VPUS[datastream]:
        raise Failed(
            Check(
                "divides",
                "fail",
                f"{datastream} does not run VPU {vpus[0]}, so there is no realization "
                "to update.",
            )
        )
    return ids, vpus[0], Check("divides", "pass", f"{len(ids)} divides in VPU {vpus[0]}")


# ── the merge ───────────────────────────────────────────────────────


def modules(block: dict) -> List[dict]:
    formulations = block.get("formulations") or []
    return (formulations[0].get("params") or {}).get("modules") or [] if formulations else []


def model_params(block: dict) -> Dict[str, dict]:
    """Map model_type_name to model_params for one realization block."""
    found = {}
    for module in modules(block):
        params = module.get("params") or {}
        if params.get("model_type_name") and params.get("model_params"):
            found[params["model_type_name"]] = dict(params["model_params"])
    return found


def contributed_parameters(realization: dict, divide_ids: List[str], kind: str) -> Dict[str, Dict[str, dict]]:
    """
    Pull calibrated parameters out of a contributed realization.

    Returns {divide_id: {model_type_name: {param: value}}}. Lumped carries one
    set in the global block; per-catchment carries a block per divide.
    """
    if kind == "lumped":
        params = model_params(realization.get("global") or {})
        if not params:
            raise Failed(
                Check(
                    "parameters",
                    "fail",
                    "The global block carries no model_params. A lumped submission must "
                    "carry its calibrated values there; values held only in BMI init "
                    "config files are not visible to this merge.",
                )
            )
        return {divide: copy.deepcopy(params) for divide in divide_ids}

    catchments = realization.get("catchments") or {}
    extracted = {d: model_params(catchments[d]) for d in divide_ids if catchments.get(d)}
    missing = sorted(set(divide_ids) - {d for d, p in extracted.items() if p})
    if missing:
        raise Failed(
            Check(
                "parameters",
                "fail",
                f"{len(missing)} divide(s) in the geopackage have no model_params in the "
                f"realization, for example: {', '.join(missing[:5])}. They would deploy "
                "uncalibrated.",
            )
        )
    return extracted


def _same(a, b) -> bool:
    """
    Whether two model_params values mean the same number.

    The live realization holds SLOTH's declarations as `0` where a contributed
    one holds `"0.0"`. ngen passes numbers to a BMI and skips anything else, so
    overwriting the first with the second would silently drop them.
    """
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if a == b:
        return True
    try:
        return a is not None and b is not None and float(a) == float(b)
    except (TypeError, ValueError):
        return False


def merge(live: dict, parameters: Dict[str, Dict[str, dict]]) -> Tuple[dict, Check]:
    """
    Write contributed parameters into a copy of the live realization.

    Each divide gets a catchment entry derived from the live global block, with
    the values written into the matching module. A contribution that changes
    nothing, because it names no module this realization runs or only repeats
    what is deployed, fails rather than deploying as a no-op.
    """
    merged = copy.deepcopy(live)
    catchments = merged.setdefault("catchments", {})
    applied = 0

    for divide, by_model in parameters.items():
        entry = copy.deepcopy(catchments.get(divide) or merged.get("global") or {})
        for module in modules(entry):
            params = module.setdefault("params", {})
            values = by_model.get(params.get("model_type_name"))
            if not values:
                continue
            current = params.setdefault("model_params", {})
            for name, value in values.items():
                if not _same(current.get(name), value):
                    current[name] = value
                    applied += 1
        catchments[divide] = entry

    if not applied:
        contributed = sorted({m for by_model in parameters.values() for m in by_model})
        raise Failed(
            Check(
                "merge",
                "fail",
                f"Merging changed nothing. This realization either runs none of "
                f"{', '.join(contributed)}, or already carries these values.",
            )
        )
    return merged, Check("merge", "pass", f"{len(parameters)} catchments, {applied} values written")


def check_schema(realization: dict, name: str) -> Check:
    """Schema only. The paths a realization names exist on the instance, not here."""
    try:
        from ngen.config.realization import NgenRealization
    except ImportError:
        return Check(name, "fail", "ngen-cal is not installed")
    try:
        NgenRealization.parse_obj(realization)
    except Exception as exc:
        return Check(name, "fail", f"{exc}")
    return Check(name, "pass", "Satisfies the ngen-cal NgenRealization model")


# ── running it ──────────────────────────────────────────────────────


def live_url(datastream: str, vpu: str) -> str:
    return f"https://{BUCKET}.s3.amazonaws.com/" + REALIZATION.format(datastream=datastream, vpu=vpu)


def build(spec: dict, workdir: Path) -> Tuple[dict, str, List[Check]]:
    """Every check from the contribution file to a merged realization."""
    checks = [check_unchanged(spec)]
    if not checks[0].ok:
        raise Failed(checks[0])

    archive = workdir / "package.bin"
    sha, check = download(spec["url"], archive)
    checks.append(check)

    extracted = workdir / "extracted"
    checks.append(unpack(archive, extracted))

    gpkg, realization_path, check = find_files(extracted, spec.get("subdir"))
    checks.append(check)

    divide_ids, spec["vpu"], check = divides(gpkg, spec["datastream"])
    checks.append(check)

    contributed = json.loads(realization_path.read_text())
    checks.append(check_schema(contributed, "contributed_schema"))

    with get(live_url(spec["datastream"], spec["vpu"])) as response:
        live = json.load(response)
    checks.append(Check("live", "pass", live_url(spec["datastream"], spec["vpu"])))

    parameters = contributed_parameters(contributed, divide_ids, spec["type"])
    checks.append(
        Check("parameters", "pass", f"{spec['type']}: " + ", ".join(sorted(next(iter(parameters.values())))))
    )

    merged, check = merge(live, parameters)
    checks.append(check)
    checks.append(check_schema(merged, "merged_schema"))
    return merged, sha, checks


def record(spec: dict, **extra) -> str:
    """The contribution as JSON, for the workflow to read and for provenance."""
    return json.dumps(
        {**spec, "last_updated": utc(spec["last_updated"]).isoformat(), **extra}, indent=2
    ) + "\n"


def cmd_check(args) -> int:
    spec = load(Path(args.contribution))
    merged, sha, checks = build(spec, Path(args.workdir))
    for check in checks:
        print(check)
    if args.out:
        Path(args.out).write_text(json.dumps(merged, indent=2) + "\n")
        print(f"[PASS] candidate: {args.out}")
    if args.record:
        Path(args.record).write_text(record(spec, package_sha256=sha))
    return 0 if all(c.ok for c in checks) else 1


def cmd_deploy(args) -> int:
    """Archive the live realization, overwrite it, and record what happened."""
    import boto3

    spec = load(Path(args.contribution))
    merged, sha, checks = build(spec, Path(args.workdir))
    for check in checks:
        print(check)
    if not all(c.ok for c in checks):
        return 1

    body = (json.dumps(merged, indent=2) + "\n").encode()
    digest = hashlib.sha256(body).hexdigest()
    key = REALIZATION.format(datastream=spec["datastream"], vpu=spec["vpu"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if args.dry_run:
        print(Check("deploy", "pass", f"Would write s3://{BUCKET}/{key}"))
        return 0

    s3 = boto3.client("s3")
    s3.copy_object(
        Bucket=BUCKET,
        CopySource={"Bucket": BUCKET, "Key": key},
        Key=ARCHIVE.format(
            datastream=spec["datastream"], vpu=spec["vpu"], stamp=stamp, commit=args.commit[:8]
        ),
    )
    s3.put_object(Bucket=BUCKET, Key=key, Body=body, ContentType="application/json")

    landed = hashlib.sha256(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()).hexdigest()
    if landed != digest:
        print(Check("deploy", "fail", f"Live object is {landed[:16]}, expected {digest[:16]}"))
        return 1

    s3.put_object(
        Bucket=BUCKET,
        Key=PROVENANCE.format(datastream=spec["datastream"], issue=spec["issue"]),
        Body=record(
            spec, package_sha256=sha, realization_sha256=digest,
            deployed_utc=stamp, commit=args.commit,
        ).encode(),
        ContentType="application/json",
    )
    print(Check("deploy", "pass", f"s3://{BUCKET}/{key} @ {digest[:16]}..."))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="research_datastream.contribution_parameters")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Validate and build the merged realization")
    check.add_argument("contribution")
    check.add_argument("--workdir", default="./contribution-work")
    check.add_argument("--out", default="", help="Write the merged realization here")
    check.add_argument("--record", default="", help="Write the resolved contribution here")
    check.set_defaults(func=cmd_check)

    deploy = sub.add_parser("deploy", help="Write the merged realization to S3")
    deploy.add_argument("contribution")
    deploy.add_argument("--workdir", default="./contribution-work")
    deploy.add_argument("--commit", default="")
    deploy.add_argument("--dry-run", action="store_true")
    deploy.set_defaults(func=cmd_deploy)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Failed as failure:
        print(failure.check)
        return 1


if __name__ == "__main__":
    sys.exit(main())
