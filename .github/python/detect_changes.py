#!/usr/bin/env python3
"""
detect_changes.py — detect-changes job for outputs-diff.yml

Inspects the git diff for modified (not new) execution JSONs. For each changed
file it parses the full datastreamcli command from both the old and new versions
and reports any simulation-relevant changes — env var tags (DS_TAG, NGIAB_TAG,
FP_TAG …), forcing flags (-F, -N, -R, -g, --FORCING_SOURCE), processor count
(-n), time flags (-s, -e), or anything else that affects the simulation itself.

Non-simulation params (--S3_PREFIX, --S3_BUCKET, -d, SKIP_VALIDATION) are
excluded from the change check so that a pure output-path rename doesn't trigger
a full re-run.

Reads from environment:
  BASE_REF      — git base ref (e.g. "main")
  S3_BUCKET     — S3 bucket name
  GITHUB_OUTPUT — path to GitHub Actions output file

Writes to $GITHUB_OUTPUT:
  has_version_change  — "true" / "false"
  templates_json      — JSON array of {file, slug} objects for each changed template
  vpus_json           — JSON array of VPU identifiers
  date                — baseline date YYYYMMDD
  changes_summary     — pipe-separated list of what changed (for PR comment)
"""

import boto3
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _short_range import apply_short_range_vars

base_ref  = os.environ["BASE_REF"]
bucket    = os.environ.get("S3_BUCKET", "ciroh-community-ngen-datastream")
gh_output = os.environ["GITHUB_OUTPUT"]

# Only execution JSONs that invoke datastreamcli are tested here.
# Forcingprocessor and other tools have their own separate workflows.
DATASTREAMCLI_MARKER = "datastreamcli/scripts/datastream"

# Changes to these params don't affect simulation outputs.
EXCLUDED_ENV = {"SKIP_VALIDATION"}
EXCLUDED_CLI = {"--S3_PREFIX", "--S3_BUCKET", "-d"}


def write_output(**kwargs):
    with open(gh_output, "a") as f:
        for k, v in kwargs.items():
            f.write(f"{k}={v}\n")


def is_datastreamcli_exec(data):
    """Return True if the execution JSON invokes datastreamcli."""
    return DATASTREAMCLI_MARKER in data.get("commands", [""])[0]


def parse_command(data):
    """Return (env_vars, cli_args) dicts parsed from the datastreamcli command."""
    cmd = data["commands"][0]

    # Strip the runuser -l ec2-user -c '...' wrapper
    m = re.search(r"-c '(.+)'$", cmd, re.DOTALL)
    inner = m.group(1) if m else cmd

    # Split at && into the export section and the datastream invocation
    if "&&" in inner:
        export_part, cli_part = inner.split("&&", 1)
    else:
        export_part, cli_part = "", inner

    # Parse "export VAR=val VAR2=val2 ..."
    env_vars = {}
    for m in re.finditer(r"(\w+)=([^\s]+)", export_part.replace("export", "")):
        env_vars[m.group(1)] = m.group(2)

    # Parse CLI flag-value pairs; skip the executable (index 0).
    # All datastreamcli flags take exactly one value.
    tokens = cli_part.strip().split()
    cli_args = {}
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("-"):
            if i + 1 < len(tokens):
                cli_args[tok] = tokens[i + 1]
                i += 2
            else:
                cli_args[tok] = ""
                i += 1
        else:
            i += 1

    return env_vars, cli_args


def find_sim_changes(old_data, new_data):
    """Return list of human-readable strings for simulation-relevant changes."""
    old_env, old_cli = parse_command(old_data)
    new_env, new_cli = parse_command(new_data)

    changes = []

    for k in sorted((set(old_env) | set(new_env)) - EXCLUDED_ENV):
        old_v, new_v = old_env.get(k), new_env.get(k)
        if old_v == new_v:
            continue
        if old_v is None:
            changes.append(f"env {k}: (added) {new_v}")
        elif new_v is None:
            changes.append(f"env {k}: (removed, was {old_v})")
        else:
            changes.append(f"env {k}: {old_v} -> {new_v}")

    for k in sorted((set(old_cli) | set(new_cli)) - EXCLUDED_CLI):
        old_v, new_v = old_cli.get(k), new_cli.get(k)
        if old_v == new_v:
            continue
        if old_v is None:
            changes.append(f"arg {k}: (added) {new_v}")
        elif new_v is None:
            changes.append(f"arg {k}: (removed, was {old_v})")
        else:
            changes.append(f"arg {k}: {old_v} -> {new_v}")

    return changes


# All VPUs in the standard CONUS configuration (17 excluded — known issues).
ALL_VPUS = ["01","02","03N","03S","03W","04","05","06","07","08","09",
            "10L","10U","11","12","13","14","15","16","18"]

# ── 1. Find modified template JSONs (--diff-filter=M skips new files) ─────────
diff_files = subprocess.run(
    ["git", "diff", "--name-only", "--diff-filter=M", f"origin/{base_ref}...HEAD"],
    capture_output=True, text=True, check=True,
).stdout.splitlines()

changed = [
    f for f in diff_files
    if re.search(r"executions/templates/.*\.json$", f)
]

if not changed:
    print("No modified execution templates — skipping.")
    write_output(has_version_change="false")
    sys.exit(0)

# ── 2. Find ALL datastreamcli templates with simulation-relevant changes ───────
found_templates = []  # list of (fpath, changes_list)
skipped_non_ds  = []

for fpath in changed:
    old_content = subprocess.run(
        ["git", "show", f"origin/{base_ref}:{fpath}"],
        capture_output=True, text=True, check=True,
    ).stdout
    with open(fpath) as f:
        new_data = json.load(f)

    if not is_datastreamcli_exec(new_data):
        skipped_non_ds.append(fpath)
        continue

    file_changes = find_sim_changes(json.loads(old_content), new_data)
    if file_changes:
        found_templates.append((fpath, file_changes))

if skipped_non_ds:
    print("Skipped (not a datastreamcli template — handled by a separate workflow):")
    for f in skipped_non_ds:
        print(f"  {f}")

if not found_templates:
    print("No datastreamcli simulation-relevant changes detected — skipping.")
    write_output(has_version_change="false")
    sys.exit(0)

for fpath, file_changes in found_templates:
    print(f"Simulation-relevant changes in template: {fpath}")
    for c in file_changes:
        print(f"  {c}")

# ── 3. Derive short_range/00/ S3 prefix for the production baseline ────────────
# Use the first changed template to locate production data; all templates share
# the same baseline date so one lookup is sufficient.
with open(found_templates[0][0]) as fh:
    template_data = json.load(fh)

sample_cmd = apply_short_range_vars(template_data["commands"][0], vpu="01")
m = re.search(r"--S3_PREFIX\s+([^\s'\"]+)", sample_cmd)
if not m:
    print("ERROR: --S3_PREFIX not found in template")
    sys.exit(1)
s3_prefix_tpl = m.group(1)
print(f"Short-range S3_PREFIX template (VPU_01): {s3_prefix_tpl}")

# ── 4. Find most recent date with production short_range data ──────────────────
s3         = boto3.client("s3", region_name="us-east-1")
found_date = None

for days_ago in range(1, 6):
    date   = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y%m%d")
    prefix = s3_prefix_tpl.replace("ngen.DAILY", f"ngen.{date}")
    key    = f"{prefix}/ngen-run.tar.gz"
    try:
        s3.head_object(Bucket=bucket, Key=key)
        print(f"Found ({days_ago}d ago): s3://{bucket}/{key}")
        found_date = date
        break
    except Exception:
        print(f"Not found ({days_ago}d ago): s3://{bucket}/{key}")

if not found_date:
    print("ERROR: no production short_range ngen-run.tar.gz found in past 1-5 days")
    sys.exit(1)

template_meta = [
    (fpath, os.path.splitext(os.path.basename(fpath))[0], file_changes)
    for fpath, file_changes in found_templates
]
templates_json = json.dumps([{"file": p, "slug": s} for p, s, _ in template_meta])
all_changes    = [f"[{s}] {c}" for _, s, cs in template_meta for c in cs]

write_output(
    has_version_change="true",
    templates_json=templates_json,
    vpus_json=json.dumps(ALL_VPUS),
    date=found_date,
    changes_summary=" | ".join(all_changes),
)
