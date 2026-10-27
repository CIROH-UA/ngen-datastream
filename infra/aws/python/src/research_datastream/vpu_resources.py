#!/usr/bin/env python3
"""
What a datastream's VPU executions read, from the Terraform that schedules them.

    python -m research_datastream.vpu_resources uris cfe-nom 16 17
    python -m research_datastream.vpu_resources settings cfe-nom

`uris` prints `VPU geopackage_s3_uri bmi_configs_s3_uri` per VPU, from the
vpu_resources locals of the datastream's main.tf: the defaults merged with any
vpu_resource_overrides entry. A datastream without BMI configurations prints
`-` in that column. `settings` prints the datastreamcli tag (`ds_tag=`) and the
realization (`realization=`, with `${vpu}` left for each VPU to fill) its
execution template runs.

Author: Jordan Laser
jlaser@lynker.com
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, Optional

from research_datastream.contribution_common import BUCKET

NRDS = Path(__file__).resolve().parents[3] / "terraform/services/nrds"

BLOCK = r'\{((?:\s*\w+\s*=\s*"[^"]*")*)\s*\}'


def resources(datastream: str, vpu: str, main_tf: Optional[str] = None) -> Dict[str, str]:
    """{name: S3 key} for one VPU, e.g. {"geopackage": ..., "bmi_configs": ...}."""
    if main_tf is None:
        main_tf = (NRDS / "datastreams" / datastream / "main.tf").read_text()
    tf = re.sub(r"#.*", "", main_tf)
    default = re.search(rf"merge\({BLOCK}", tf)
    if default is None:
        raise SystemExit(f"{datastream}: main.tf has no vpu_resources defaults")
    override = re.search(rf'"{re.escape(vpu)}"\s*=\s*{BLOCK}', tf)
    pairs = default.group(1) + (override.group(1) if override else "")
    return {k: v.replace("${vpu}", vpu) for k, v in re.findall(r'(\w+)\s*=\s*"([^"]*)"', pairs)}


def settings(datastream: str, template: Optional[str] = None) -> Dict[str, str]:
    """{"ds_tag": ..., "realization": ...} from the datastream's execution template."""
    if template is None:
        paths = sorted((NRDS / "datastreams" / datastream / "templates").glob("*.tpl"))
        if not paths:
            raise SystemExit(f"{datastream}: no execution template")
        template = paths[0].read_text()
    tag = re.search(r"DS_TAG=([^\s&']+)", template)
    realization = re.search(r"(?<!\S)-R\s+([^\s']+)", template)
    if not tag or not realization:
        raise SystemExit(f"{datastream}: the template has no DS_TAG or -R")
    return {"ds_tag": tag.group(1), "realization": realization.group(1).replace("${s3_bucket}", BUCKET)}


def s3_uri(key: str) -> str:
    return f"s3://{BUCKET}/{key}"


def cmd_uris(args) -> None:
    for vpu in args.vpus:
        found = resources(args.datastream, vpu)
        bmi = s3_uri(found["bmi_configs"]) if "bmi_configs" in found else "-"
        print(vpu, s3_uri(found["geopackage"]), bmi)


def cmd_settings(args) -> None:
    for key, value in settings(args.datastream).items():
        print(f"{key}={value}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    u = sub.add_parser("uris", help="print each VPU's geopackage and BMI configuration URIs")
    u.add_argument("datastream", help="directory under services/nrds/datastreams")
    u.add_argument("vpus", nargs="+")
    u.set_defaults(func=cmd_uris)

    s = sub.add_parser("settings", help="print the template's ds_tag and realization")
    s.add_argument("datastream", help="directory under services/nrds/datastreams")
    s.set_defaults(func=cmd_settings)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
