#!/usr/bin/env python3
"""
Build one test execution per run type and VPU for an NRDS datastream, from the executions
Terraform would schedule in production.

    python -m research_datastream.vpu_test targets cfe-nom lstm_0 --main-tf main.tf
    python -m research_datastream.vpu_test select plan.json cfe-nom --main-tf main.tf --out-dir execs

`targets` prints the Terraform module address of each datastream directory.
`select` reads `terraform show -json` of a plan that includes those modules,
keeps one schedule per run type and VPU, and rewrites it to run on a fixed past date and
write under a test prefix. Nothing here knows a particular datastream: the
template, instance sizes and run options are the ones production uses.

Author: Jordan Laser
jlaser@lynker.com
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

TEST_ROOT = "test/cicd/vpu-test"
TEST_TAG = "nrds_vpu_test"

MODULE_RE = re.compile(r'module\s+"(\w+)"\s*\{\s*source\s*=\s*"\./datastreams/([^"]+)"')
BUCKET_RE = re.compile(r"(?i)--s3_bucket[=\s']+([^\s']+)")
PREFIX_RE = re.compile(r"(?i)(--s3_prefix[=\s']+)([^\s']+)")
FORCING_RE = re.compile(r"(?i)(?<!\S)-F[=\s']+([^\s']+)")
VPU_RE = re.compile(r"VPU_(\d{2}[A-Z]?)\b")
INIT_RE = re.compile(r"(?:fcst|init)(\d{2})")
DAILY_RE = re.compile(r"(?<![A-Za-z0-9])DAILY(?![A-Za-z0-9])")
START_DAILY_RE = re.compile(r"(-s\s+)DAILY(?![A-Za-z0-9])")


def module_addresses(main_tf: Path) -> Dict[str, str]:
    """Datastream directory name -> module address, from the nrds main.tf."""
    return {d: f"module.{m}" for m, d in MODULE_RE.findall(main_tf.read_text())}


def schedules(plan: dict, address: str) -> List[dict]:
    """The planned aws_scheduler_schedule values under one module."""
    out = []
    for child in plan.get("planned_values", {}).get("root_module", {}).get("child_modules", []):
        if child.get("address") != address:
            continue
        for res in child.get("resources", []):
            if res.get("type") == "aws_scheduler_schedule":
                out.append(res["values"])
    return out


def to_url(path: str) -> str:
    m = re.match(r"s3://([^/]+)/(.+)", path)
    return f"https://{m.group(1)}.s3.amazonaws.com/{m.group(2)}" if m else path


def exists(url: str) -> bool:
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=20):
            return True
    except (urllib.error.URLError, TimeoutError):
        return False


def rewrite(execution: dict, date: str, prefix_root: str) -> dict:
    """Pin DAILY to `date` and move the output under `prefix_root`.

    With DAILY gone from the S3 prefix the commander leaves the date alone,
    so the run is the same whatever hour it starts.
    """
    ex = json.loads(json.dumps(execution))
    commands = []
    for cmd in ex["commands"]:
        cmd = PREFIX_RE.sub(lambda m: f"{m.group(1)}{prefix_root}/{m.group(2)}", cmd)
        if " -e " not in cmd:
            cmd = START_DAILY_RE.sub(rf"\g<1>DAILY -e {date}0000", cmd)
        cmd = START_DAILY_RE.sub(r"\g<1>__START__", cmd)
        cmd = DAILY_RE.sub(date, cmd).replace("__START__", "DAILY")
        commands.append(cmd)
    ex["commands"] = commands
    for spec in ex.get("instance_parameters", {}).get("TagSpecifications", []):
        for tag in spec.get("Tags", []):
            if tag["Key"] == "Project":
                tag["Value"] = TEST_TAG
            elif tag["Key"] == "Name":
                tag["Value"] = f"vputest_{tag['Value']}"
    return ex


def first(pattern: re.Pattern, commands: List[str], group: int = 1) -> Optional[str]:
    for cmd in commands:
        m = pattern.search(cmd)
        if m:
            return m.group(group)
    return None


def pick(candidates: List[dict], run_types: List[str], vpus: Optional[List[str]]) -> Dict[tuple, dict]:
    """One schedule per (run type, VPU).

    A run type is scheduled once per init cycle (short_range 24 times a day), so
    each VPU has several to choose from. Init 00 is used where the run type has
    it, otherwise its earliest init (analysis_assim_extend runs only at 16).
    """
    chosen: Dict[tuple, tuple] = {}
    for sched in candidates:
        run_type = next((rt for rt in run_types if sched["name"].startswith(f"{rt}_")), None)
        if run_type is None:
            continue
        target = json.loads(sched["target"][0]["input"])
        execution = json.loads(target["Input"])
        vpu = first(VPU_RE, execution["commands"])
        if vpu is None or (vpus and vpu not in vpus):
            continue
        init = (INIT_RE.search(sched["name"]) or [None, "99"])[1]
        rank = (init, sched["name"])
        key = (run_type, vpu)
        if key not in chosen or rank < chosen[key][0]:
            chosen[key] = (rank, sched["name"], target["StateMachineArn"], execution)
    return {
        key: {"schedule": name, "state_machine_arn": arn, "execution": ex}
        for key, (_, name, arn, ex) in sorted(chosen.items())
    }


def pick_date(selected: Dict[tuple, dict], date: Optional[str], days_back: int) -> str:
    """The most recent day, from yesterday back, with every VPU's forcing."""
    if date:
        return date
    today = datetime.now(timezone.utc)
    for back in range(1, days_back + 1):
        day = (today - timedelta(days=back)).strftime("%Y%m%d")
        forcings = [first(FORCING_RE, s["execution"]["commands"]) for s in selected.values()]
        urls = [to_url(DAILY_RE.sub(day, f)) for f in forcings if f]
        if all(exists(u) for u in urls):
            return day
        print(f"{day}: forcing missing for at least one VPU", file=sys.stderr)
    raise SystemExit(f"No day in the last {days_back} has forcing for every selected VPU.")


def cmd_targets(args) -> None:
    addresses = module_addresses(args.main_tf)
    for ds in args.datastreams:
        if ds not in addresses:
            raise SystemExit(f"{ds}: no module in {args.main_tf} sources ./datastreams/{ds}")
        print(f"-target={addresses[ds]}")


def cmd_select(args) -> None:
    plan = json.loads(args.plan.read_text())
    address = module_addresses(args.main_tf).get(args.datastream)
    if address is None:
        raise SystemExit(f"{args.datastream}: not a datastream module in {args.main_tf}")
    vpus = args.vpus.split() if args.vpus else None
    planned = schedules(plan, address)
    if not planned:
        raise SystemExit(f"{args.datastream}: the plan has no schedules under {address}; was it targeted?")
    run_types = args.run_types.split()
    selected = pick(planned, run_types, vpus)
    if not selected:
        print(f"{args.datastream}: no per-VPU {' or '.join(run_types)} schedule, nothing to test", file=sys.stderr)
        print("[]")
        return
    date = pick_date(selected, args.date, args.days_back)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9]", "", args.datastream)
    matrix = []
    for (run_type, vpu), sel in selected.items():
        prefix_root = f"{TEST_ROOT}/{args.run_id}"
        ex = rewrite(sel["execution"], date, prefix_root)
        out = args.out_dir / f"{slug}_{run_type}_VPU_{vpu}.json"
        out.write_text(json.dumps(ex, indent=2))
        matrix.append({
            "datastream": args.datastream,
            "run_type": run_type,
            "vpu": vpu,
            "schedule": sel["schedule"],
            "date": date,
            "file": out.name,
            "state_machine_arn": sel["state_machine_arn"],
            "s3_bucket": first(BUCKET_RE, ex["commands"]),
            "s3_prefix": first(PREFIX_RE, ex["commands"], 2),
            "name": f"vputest_{slug}_{run_type}_{vpu}_{args.run_id}"[:80],
        })
    print(json.dumps(matrix))


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("targets", help="print -target flags for datastream directories")
    t.add_argument("datastreams", nargs="+")
    t.add_argument("--main-tf", type=Path, required=True)
    t.set_defaults(func=cmd_targets)

    s = sub.add_parser("select", help="write one test execution per run type and VPU and print the matrix")
    s.add_argument("plan", type=Path, help="terraform show -json output")
    s.add_argument("datastream", help="directory under services/nrds/datastreams")
    s.add_argument("--main-tf", type=Path, required=True)
    s.add_argument("--out-dir", type=Path, required=True)
    s.add_argument("--run-types", default="short_range", help="space-separated, e.g. 'short_range medium_range'")
    s.add_argument("--vpus", help="space-separated VPUs, default all")
    s.add_argument("--date", help="YYYYMMDD, default the latest day with forcing")
    s.add_argument("--days-back", type=int, default=5)
    s.add_argument("--run-id", default="local")
    s.set_defaults(func=cmd_select)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
