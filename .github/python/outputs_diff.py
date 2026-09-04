#!/usr/bin/env python3
"""Outputs-diff regression check. Renders a datastream execution template, re-runs
it against a production baseline date, and diffs the troute parquet.

Subcommands: vpus | changes | render | run | compare | report.
See docs/nrds/OUTPUTS_DIFF.md."""

import argparse, json, os, re, subprocess, sys, tempfile, time
from datetime import datetime, timedelta, timezone

try:  # only `run` and `compare` need these
    import boto3, numpy as np, pandas as pd
except ImportError:
    pass

ROOT   = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                        capture_output=True, text=True, check=True).stdout.strip()
DS_DIR = f"{ROOT}/infra/aws/terraform/services/nrds/datastreams"
TFVARS = f"{ROOT}/infra/aws/terraform/services/nrds/envs/prod.tfvars"
RENDER = f"{ROOT}/.github/outputs-diff/render"

SUPPORTED = ["cfe-nom", "lstm_0", "routing-only"]  # the datastreamcli datastreams
TROUTE    = "ngen-run/outputs/troute"
REGION    = "us-east-1"
MARKER    = "datastreamcli/scripts/datastream"
KEYS      = ["feature_id", "time", "type"]         # troute parquet primary key
EXCLUDED  = {"SKIP_VALIDATION", "--S3_PREFIX", "--S3_BUCKET", "-d"}  # cannot alter outputs
ICON      = {"IDENTICAL": "✅", "WITHIN_TOL": "✅", "DIFFERS": "⚠️", "ERROR": "❌"}
RANK      = {"IDENTICAL": 0, "WITHIN_TOL": 1, "DIFFERS": 2, "ERROR": 3}

RUN_TYPES = {
    "short_range":           dict(run_type_l="short_range", run_type_h="SHORT_RANGE",
                                  fcst="f001_f018", member="", member_suffix="", member_path=""),
    "medium_range":          dict(run_type_l="medium_range", run_type_h="MEDIUM_RANGE",
                                  fcst="f001_f240", member="1", member_suffix="_1", member_path="/1"),
    "analysis_assim_extend": dict(run_type_l="analysis_assim_extend", run_type_h="ANALYSIS_ASSIM_EXTEND",
                                  fcst="tm27_tm00", member="", member_suffix="", member_path=""),
}


# ── helpers ──────────────────────────────────────────────────────────────────
def die(msg):
    sys.exit(f"::error::{msg}")


def only(d, what):
    """The single expected file in a directory."""
    f = sorted(x for x in os.listdir(d) if not x.startswith("."))
    if len(f) != 1:
        die(f"expected one {what} in {d}, found {f}")
    return f"{d}/{f[0]}"


def gh_output(**kw):
    if p := os.environ.get("GITHUB_OUTPUT"):
        with open(p, "a") as f:
            f.writelines(f"{k}={v}\n" for k, v in kw.items())


def tf_block(text, name):
    """The `name = { ... }` block from a .tf file, by brace matching."""
    i = text.find(f"{name} = {{")
    if i < 0:
        die(f"no local {name} in schedules.tf")
    i, depth = text.index("{", i), 0
    for j in range(i, len(text)):
        depth += (text[j] == "{") - (text[j] == "}")
        if not depth:
            return text[i:j + 1]
    die(f"unbalanced braces in {name}")


def tfvars():
    pat = re.compile(r'\s*([a-z_0-9]+)\s*=\s*"?([^"#\n]*?)"?\s*(?:#.*)?$')
    return {m[1]: m[2] for line in open(TFVARS) if (m := pat.match(line)) and m[2]}


def vpus_of(ds, run_type):
    """local.vpus if the module declares one, else the config's instance_types keys."""
    if os.path.exists(main := f"{DS_DIR}/{ds}/main.tf"):
        # Anchored so a sibling like `excluded_vpus = [...]` cannot match instead.
        if m := re.search(r"^\s*vpus\s*=\s*\[(.*?)\]", open(main).read(), re.S | re.M):
            return re.findall(r'"([^"]+)"', m[1])
    return list(json.load(open(only(f"{DS_DIR}/{ds}/config", "config")))[run_type]["instance_types"])


# ── render ───────────────────────────────────────────────────────────────────
def render(ds, vpu, init, run_type):
    """Render the template through terraform's own templatefile(), as schedules.tf does."""
    tf  = open(f"{DS_DIR}/{ds}/schedules.tf").read()
    cfg = json.load(open(only(f"{DS_DIR}/{ds}/config", "config")))[run_type]
    tv, tok = tfvars(), ds.replace("-", "_")

    if vpu not in cfg["instance_types"]:
        die(f"VPU {vpu} not configured for {ds} {run_type}; known: {list(cfg['instance_types'])}")
    itype = cfg["instance_types"][vpu]

    # Catch a bad init here rather than after an EC2 instance has already been paid for.
    if (cycles := cfg.get("init_cycles")) and init not in cycles:
        die(f"init {init} not in {ds} {run_type} init_cycles; known: {cycles}")

    # nprocs is either pinned in schedules.tf (routing-only) or vCPUs - 1.
    if m := re.search(r"nprocs\s*=\s*(\d+)\s*$", tf_block(tf, f"{run_type}_{tok}_config"), re.M):
        nprocs = m[1]
    else:
        if not (vm := re.search(r"instance_vcpus\s*=\s*\{(.*?)\}", tf, re.S)):
            die(f"{ds} pins no nprocs and declares no instance_vcpus map in schedules.tf")
        vcpu = dict(re.findall(r'"([^"]+)"\s*=\s*(\d+)', vm[1]))
        if itype not in vcpu:
            die(f"no instance_vcpus entry for {itype}")
        nprocs = str(int(vcpu[itype]) - 1)

    for k in (f"{tok}_ami_id", "profile_name", "environment_suffix", "s3_bucket"):
        if k not in tv:
            die(f"{k} missing from {TFVARS}")

    tvars = {**RUN_TYPES[run_type], "vpu": vpu, "init": init, "nprocs": nprocs,
             "ami_id": tv[f"{tok}_ami_id"], "instance_type": itype,
             "instance_profile": tv["profile_name"], "volume_size": str(cfg["volume_size"]),
             "environment_suffix": tv["environment_suffix"], "s3_bucket": tv["s3_bucket"]}
    i = tf.find(f"for_each = local.{run_type}_{tok}_config")
    if i >= 0 and (m := re.search(r"timeout_s\s*=\s*(\d+)", tf[i:])):
        tvars["timeout_s"] = m[1]

    tpl = only(f"{DS_DIR}/{ds}/templates", "template")
    with tempfile.TemporaryDirectory() as tmp:
        json.dump({"template_path": tpl, "template_vars": tvars}, open(f"{tmp}/v.json", "w"))
        env = {**os.environ, "TF_DATA_DIR": f"{tmp}/.tf", "TF_IN_AUTOMATION": "1"}
        rendered = ""
        for a in (["init", "-backend=false"],
                  ["apply", "-auto-approve", f"-var-file={tmp}/v.json", f"-state={tmp}/s"],
                  ["output", f"-state={tmp}/s", "-raw", "rendered"]):
            quiet = [] if a[0] == "output" else ["-input=false"]
            p = subprocess.run(["terraform", f"-chdir={RENDER}", *a, *quiet],
                               capture_output=True, text=True, env=env)
            if p.returncode:
                die(f"terraform {a[0]} failed:\n{p.stderr}")
            rendered = p.stdout

    # A leftover ${...} means the template gained a variable we do not set.
    if left := sorted(set(re.findall(r"\$\{([a-z_]+)\}", rendered))):
        die(f"unresolved template variables {left} in {tpl}")
    return json.loads(rendered)


# ── run ──────────────────────────────────────────────────────────────────────
def baseline_date(s3, bucket, daily, days):
    """Most recent date whose production run left troute parquet on S3."""
    for d in range(1, days + 1):
        date = (datetime.now(timezone.utc) - timedelta(days=d)).strftime("%Y%m%d")
        pfx  = daily.replace("ngen.DAILY", f"ngen.{date}")
        got  = s3.list_objects_v2(Bucket=bucket, Prefix=f"{pfx}/{TROUTE}/", MaxKeys=10)
        if any(o["Key"].endswith(".parquet") for o in got.get("Contents", [])):
            print(f"baseline {date} ({d}d ago)")
            return date
        print(f"  no output {d}d ago: {pfx}")
    die(f"no production troute parquet in the past {days} days")


def cmd_run(a):
    ex = render(a.datastream, a.vpu, a.init, a.run_type)
    if not (m := re.search(r"--S3_PREFIX\s+([^\s'\"]+)", ex["commands"][0])):
        die("--S3_PREFIX not found in rendered execution")
    s3   = boto3.client("s3", region_name=REGION)
    date = a.date or baseline_date(s3, a.bucket, m[1], a.max_days_back)
    prod = m[1].replace("ngen.DAILY", f"ngen.{date}")
    test = f"test/outputs_diff/{a.run_id}/{a.datastream}/VPU_{a.vpu}"

    cmds = []
    for c in ex["commands"]:
        c = c.replace("ngen.DAILY", f"ngen.{date}")
        # With -s DAILY, datastreamcli treats -e as a run-DATE selector, not an end time
        # (configure_datastream.py: start_dt = strptime(end); start forced to 01:00). Passing
        # real -s/-e timestamps instead makes ngen read past the end of the forcing file.
        if "-s DAILY" in c and "-e " not in c:
            c = c.replace("-s DAILY", f"-s DAILY -e {date}0000")
        cmds.append(re.sub(r"--S3_PREFIX\s+[^\s'\"]+", f"--S3_PREFIX {test}", c))
    ex["commands"] = cmds
    ex["instance_parameters"]["TagSpecifications"] = [{"ResourceType": "instance", "Tags": [
        {"Key": "Name", "Value": f"outputs_diff_{a.datastream}_VPU{a.vpu}"},
        {"Key": "Project", "Value": f"outputs_diff_{a.run_id}"}]}]

    info = dict(datastream=a.datastream, vpu=a.vpu, init=a.init, run_type=a.run_type,
                date=date, bucket=a.bucket, prod_prefix=prod, test_prefix=test, troute=TROUTE)
    json.dump(ex, open("test_execution.json", "w"), indent=2)
    print(f"prod {prod}\ntest {test}\ncmd  {cmds[0][:400]}")

    if a.dry_run:
        info["status"] = "DRY_RUN"
    else:
        if not a.sm_arn:
            die("--sm-arn is required to submit")
        sfn  = boto3.client("stepfunctions", region_name=REGION)
        name = f"outputs-diff-{a.run_id}-{a.datastream}-VPU{a.vpu}-{int(time.time())}"[:80]
        arn  = sfn.start_execution(stateMachineArn=a.sm_arn, name=name,
                                   input=json.dumps(ex))["executionArn"]
        print(f"started {arn}")
        info["execution_arn"], info["status"] = arn, "TIMED_OUT"
        for el in range(0, a.timeout_s, 30):
            st = sfn.describe_execution(executionArn=arn)["status"]
            print(f"[{el}s] VPU_{a.vpu}: {st}", flush=True)
            if st != "RUNNING":
                info["status"] = st
                break
            time.sleep(30)

    json.dump(info, open(a.out, "w"), indent=2)
    gh_output(**{k: info[k] for k in ("date", "prod_prefix", "test_prefix", "status")})
    if info["status"] not in ("SUCCEEDED", "DRY_RUN"):
        die(f"VPU_{a.vpu} ended {info['status']}")


# ── compare ──────────────────────────────────────────────────────────────────
def cmp_col(col, bs, ts, rtol, atol):
    b = pd.to_numeric(bs, errors="coerce").to_numpy("float64")
    t = pd.to_numeric(ts, errors="coerce").to_numpy("float64")
    nb, nt = int(np.isnan(b).sum()), int(np.isnan(t).sum())
    ok, nan_mismatch = ~np.isnan(b) & ~np.isnan(t), int((np.isnan(b) != np.isnan(t)).sum())
    s = {"nan_baseline": nb, "nan_test": nt, "nan_mismatch": nan_mismatch, "n_valid": int(ok.sum())}

    if not ok.any():
        # All-NaN on both sides is normal, e.g. nudge without data assimilation.
        s.update(verdict="ALL_NAN_BOTH" if nb == nt == len(b) else "NO_OVERLAP",
                 n_diff=0, max_abs=None, max_rel=None)
        print(f"    {col:<12} {s['verdict']:<13}{'-':>9}{'-':>13}{'-':>11}  {nb}/{nt}")
        return s

    bv, tv = b[ok], t[ok]
    ad = np.abs(tv - bv)
    nd = int((ad > atol + rtol * np.abs(bv)).sum())
    nz = np.abs(bv) > 0  # relative difference is meaningless where the baseline is 0
    mr = float((ad[nz] / np.abs(bv[nz])).max()) if nz.any() else None
    v  = ("IDENTICAL" if not nd and not ad.max() and not nan_mismatch else
          "WITHIN_TOL" if not nd and not nan_mismatch else "DIFFERS")
    s.update(verdict=v, n_diff=nd, max_abs=float(ad.max()), max_rel=mr,
             p50_abs=float(np.percentile(ad, 50)), p99_abs=float(np.percentile(ad, 99)),
             baseline_mean=float(bv.mean()), test_mean=float(tv.mean()))
    print(f"{'*** ' if v == 'DIFFERS' else '    '}{col:<12} {v:<13}{nd:>9}{ad.max():>13.6g}"
          f"{('-' if mr is None else f'{mr:.4g}'):>11}  {nb}/{nt}"
          + (f"  ({nan_mismatch} NaN mismatch)" if nan_mismatch else ""))
    return s


def read_parquet(path):
    """Read a parquet, promoting a named index to a column so it can be a join key.

    troute output carries feature_id as a column, but the NEXOUT parquets in the same
    run keep it as the index; without this they would compare as "no join key".
    """
    d = pd.read_parquet(path)
    named = [n for n in d.index.names if n is not None]
    if named and not set(named) & set(d.columns):  # reset_index() would raise on a collision
        d = d.reset_index()
    return d


def cmp_file(label, bp, tp, rtol, atol):
    print(f"\n{'='*72}\n  {label}\n{'='*72}")
    b, t = read_parquet(bp), read_parquet(tp)
    r = {"file": label, "baseline_rows": len(b), "test_rows": len(t), "columns": {}}
    print(f"  rows: {len(b)} baseline / {len(t)} test")

    if set(b.columns) != set(t.columns):
        r["error"] = "column mismatch"
        print(f"  *** COLUMN MISMATCH: {sorted(set(b.columns) ^ set(t.columns))}")
        return r
    if not (keys := [c for c in KEYS if c in b.columns]):
        r["error"] = "no join key"
        print(f"  *** no join key among {KEYS}; columns are {list(b.columns)}")
        return r
    if b.duplicated(subset=keys).any() or t.duplicated(subset=keys).any():
        r["error"] = "duplicate join keys"
        print(f"  *** duplicate keys on {keys}; cannot join safely")
        return r

    # Joined, not positional: t-route does not emit rows in a stable order.
    m = b.merge(t, on=keys, how="outer", suffixes=("_b", "_t"), indicator=True)
    r["rows_only_baseline"] = int((m["_merge"] == "left_only").sum())
    r["rows_only_test"]     = int((m["_merge"] == "right_only").sum())
    r["rows_compared"]      = int((m["_merge"] == "both").sum())
    print(f"  join {keys}: {r['rows_compared']} common, {r['rows_only_baseline']} baseline-only, "
          f"{r['rows_only_test']} test-only")
    if r["rows_only_baseline"] or r["rows_only_test"]:
        print("  *** KEY SET DIFFERS")

    common = m[m["_merge"] == "both"]
    print(f"\n    {'column':<12} {'verdict':<13}{'n_diff':>9}{'max_abs':>13}{'max_rel':>11}  nan b/t")
    for col in (c for c in b.columns if c not in keys):
        if pd.api.types.is_numeric_dtype(b[col]):
            r["columns"][col] = cmp_col(col, common[f"{col}_b"], common[f"{col}_t"], rtol, atol)
        else:
            same = common[f"{col}_b"].equals(common[f"{col}_t"])
            r["columns"][col] = {"verdict": "IDENTICAL" if same else "DIFFERS", "non_numeric": True}
            print(f"    {col:<12} {r['columns'][col]['verdict']:<13}(non-numeric)")
    return r


def cmd_compare(a):
    find = lambda root: {os.path.relpath(f"{d}/{f}", root): f"{d}/{f}"
                         for d, _, fs in os.walk(root) for f in fs if f.endswith(".parquet")}
    b, t = find(a.baseline_dir), find(a.test_dir)
    print(f"baseline {len(b)} file(s), test {len(t)} file(s)")

    if not b or not t:
        # A missing output must not look like a clean diff.
        print(f"::error::no parquet to compare (baseline={len(b)}, test={len(t)})")
        res, overall = [{"file": "-", "error": "no parquet files found", "columns": {}}], "ERROR"
    else:
        res, shared = [], sorted(set(b) & set(t))
        if not shared and len(b) == len(t):  # date-stamped names may differ
            print("NOTE: filenames differ; pairing by sorted order")
            pairs = [(f"{x} vs {y}", b[x], t[y]) for x, y in zip(sorted(b), sorted(t))]
        else:
            pairs = [(k, b[k], t[k]) for k in shared]
            for k in sorted(set(b) ^ set(t)):
                side = "baseline" if k in b else "test"
                print(f"  *** {k}: present in {side} only")
                res.append({"file": k, "error": f"present in {side} only", "columns": {}})
        res += [cmp_file(l, x, y, a.rtol, a.atol) for l, x, y in pairs]

        verdicts = [c["verdict"] for r in res for c in r["columns"].values()]
        overall = ("ERROR"    if any("error" in r for r in res) else
                   "DIFFERS"  if any(r.get("rows_only_baseline") or r.get("rows_only_test") for r in res)
                              or {"DIFFERS", "NO_OVERLAP"} & set(verdicts) else
                   "WITHIN_TOL" if "WITHIN_TOL" in verdicts else "IDENTICAL")

    print(f"\n{'='*72}\nOVERALL: {overall}  (rtol={a.rtol}, atol={a.atol})\n{'='*72}")
    meta = json.load(open(a.run_info)) if a.run_info and os.path.exists(a.run_info) else {}
    json.dump({"overall": overall, "meta": meta, "rtol": a.rtol, "atol": a.atol, "files": res},
              open(a.json_out, "w"), indent=2)


# ── report ───────────────────────────────────────────────────────────────────
def cmd_report(a):
    res = [json.load(open(f"{d}/{f}")) for d, _, fs in os.walk(a.results_dir)
           for f in fs if f == "diff_result.json"]
    if not res:
        out = "## Outputs Diff\n\nNo results — every VPU job failed before comparing.\n"
    else:
        res.sort(key=lambda r: r.get("meta", {}).get("vpu", ""))
        overall = max((r["overall"] for r in res), key=lambda v: RANK.get(v, 0))
        m = res[0].get("meta", {})
        lines = [f"## Outputs Diff {ICON.get(overall, '')} `{overall}`", "",
                 f"`{m.get('datastream', '?')}` · {m.get('run_type', '?')} · init "
                 f"{m.get('init', '?')} · baseline `{m.get('date', '?')}` · {len(res)} VPU(s) · "
                 f"rtol={res[0].get('rtol')} atol={res[0].get('atol')}", "",
                 "| VPU | verdict | rows compared | columns differing |", "|---|---|---|---|"]
        for r in res:
            rows = sum(f.get("rows_compared", 0) or 0 for f in r["files"])
            diff = ", ".join(
                f"`{c}` ({s['n_diff']} rows"
                + (f", max rel {s['max_rel']:.3g})" if s.get("max_rel") is not None else ")")
                for f in r["files"] for c, s in f["columns"].items() if s["verdict"] == "DIFFERS"
            ) or "—"
            lines.append(f"| VPU_{r.get('meta', {}).get('vpu', '?')} | "
                         f"{ICON.get(r['overall'], '')} {r['overall']} | {rows:,} | {diff} |")
        lines += ["", "`IDENTICAL` equal · `WITHIN_TOL` within tolerance · `DIFFERS` outside it "
                  "· `ERROR` could not compare. Informational only — never blocks a merge."]
        out = "\n".join(lines) + "\n"

    print(out)
    if s := os.environ.get("GITHUB_STEP_SUMMARY"):
        open(s, "a").write(out)


# ── changes ──────────────────────────────────────────────────────────────────
def parse_cmd(text):
    """Flatten a template's datastreamcli invocation to {"env X"/"arg -f": value}."""
    if not (line := next((l for l in text.splitlines() if MARKER in l), None)):
        return None
    i, out = line.find(MARKER), {}
    for k, v in re.findall(r"(\w+)=(\S+)", line[:i].replace("export", "")):
        out[f"env {k}"] = v
    tok, j = line[i:].split(), 1
    while j < len(tok):
        if tok[j].startswith("-"):
            nxt = tok[j + 1] if j + 1 < len(tok) else ""
            takes = bool(nxt) and not nxt.startswith("-")  # every flag takes one value
            out[f"arg {tok[j]}"] = nxt.rstrip("'\"") if takes else ""
            j += 2 if takes else 1
        else:
            j += 1
    return out


def cmd_changes(a):
    base, changed = (a.base_ref if "/" in a.base_ref else f"origin/{a.base_ref}"), {}
    for ds in SUPPORTED:
        rel = os.path.relpath(only(f"{DS_DIR}/{ds}/templates", "template"), ROOT)
        p = subprocess.run(["git", "show", f"{base}:{rel}"], capture_output=True, text=True)
        if p.returncode:
            print(f"{ds}: new on this branch, no baseline to diff")
            continue
        old, new = parse_cmd(p.stdout), parse_cmd(open(f"{ROOT}/{rel}").read())
        if not new:
            continue
        if not old:
            changed[ds] = ["datastreamcli invocation added"]
            continue
        ch = []
        for k in sorted(set(old) | set(new)):
            ov, nv = old.get(k), new.get(k)
            if ov == nv or k.split()[-1] in EXCLUDED:
                continue
            ch.append(f"{k}: " + (f"(added) {nv}" if ov is None else
                                  f"(removed, was {ov})" if nv is None else f"{ov} -> {nv}"))
        if ch:
            changed[ds] = ch

    for ds, ch in changed.items():
        print(f"\n{ds}:")
        print("\n".join(f"  {c}" for c in ch))
    if not changed:
        print(f"No simulation-relevant template changes vs {base}.")
    gh_output(has_changes=str(bool(changed)).lower(),
              changed_datastreams=json.dumps(sorted(changed)))


# ── vpus ─────────────────────────────────────────────────────────────────────
def cmd_vpus(a):
    known = vpus_of(a.datastream, a.run_type)
    if not a.vpus.strip():  # "all" must be explicit; a blank field should launch nothing
        die('vpus is empty; pass a VPU list or "all"')
    sel = known if a.vpus.strip().lower() == "all" else [v.strip() for v in a.vpus.split(",") if v.strip()]
    if bad := [v for v in sel if v not in known]:
        die(f"VPUs {bad} not configured for {a.datastream}; known: {known}")
    print(f"::notice::testing {len(sel)} VPU(s) of {a.datastream}: {','.join(sel)}", file=sys.stderr)
    gh_output(vpus_json=json.dumps(sel))
    print(json.dumps(sel))


# ── cli ──────────────────────────────────────────────────────────────────────
def main():
    ap  = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def target(name, summary, **kw):
        p = sub.add_parser(name, help=summary)
        p.set_defaults(**kw)
        return p

    def sim_args(p):
        p.add_argument("--datastream", required=True, choices=SUPPORTED)
        p.add_argument("--vpu", required=True)
        p.add_argument("--init", default="00")
        p.add_argument("--run-type", default="short_range", choices=list(RUN_TYPES))
        return p

    p = target("vpus", "resolve the VPU matrix", fn=cmd_vpus)
    p.add_argument("--datastream", required=True, choices=SUPPORTED)
    p.add_argument("--run-type", default="short_range", choices=list(RUN_TYPES))
    p.add_argument("--vpus", default="")

    p = target("changes", "simulation-relevant template diff vs a base ref", fn=cmd_changes)
    p.add_argument("--base-ref", default=os.environ.get("BASE_REF", "main"))

    sim_args(target("render", "print the rendered execution JSON",
                    fn=lambda a: print(json.dumps(render(a.datastream, a.vpu, a.init, a.run_type),
                                                  indent=2))))

    p = sim_args(target("run", "render, pin to a baseline date, and run it", fn=cmd_run))
    p.add_argument("--date", default="", help="baseline YYYYMMDD; discovered if omitted")
    p.add_argument("--max-days-back", type=int, default=7)
    p.add_argument("--bucket", default="ciroh-community-ngen-datastream")
    p.add_argument("--sm-arn", default="")
    p.add_argument("--run-id", default="local")
    p.add_argument("--timeout-s", type=int, default=5400)
    p.add_argument("--out", default="run_info.json")
    p.add_argument("--dry-run", action="store_true", help="render and patch, submit nothing")

    p = target("compare", "diff baseline vs test parquet", fn=cmd_compare)
    p.add_argument("--baseline-dir", required=True)
    p.add_argument("--test-dir", required=True)
    p.add_argument("--rtol", type=float, default=1e-5)
    p.add_argument("--atol", type=float, default=1e-8)
    p.add_argument("--run-info", default="")
    p.add_argument("--json-out", default="diff_result.json")

    p = target("report", "aggregate per-VPU results into the job summary", fn=cmd_report)
    p.add_argument("--results-dir", required=True)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
