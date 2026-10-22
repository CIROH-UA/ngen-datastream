#!/usr/bin/env python3
"""Run a datastream change as production runs it, short_range at a chosen date and init, and compare
its troute output with production's for the same run. See docs/nrds/OUTPUTS_DIFF.md."""
import argparse, glob, json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
import boto3, numpy as np, pandas as pd

NRDS, ACCOUNT, BUCKET = "infra/aws/terraform/services/nrds", "879381264451", "ciroh-community-ngen-datastream"
TFVARS = f"{NRDS}/envs/prod.tfvars"
SUPPORTED = ["cfe-nom", "lstm_0", "routing-only"]  # the datastreams that run datastreamcli
WATCHED = re.compile(rf"{NRDS}/datastreams/([^/]+)/(templates|config|contributions)/")
SHORT_RANGE = dict(init="00", run_type_l="short_range", run_type_h="SHORT_RANGE", fcst="f001_f018", member="",
                   member_suffix="", member_path="", restart_init="00", restart_date="DAILY", timeout_s=7200)
KEYS = ["feature_id", "time", "type"]  # troute's row key

def sh(*cmd): return subprocess.run(cmd, capture_output=True, text=True).stdout
def tfvars(text): return dict(re.findall(r'^\s*(\w+)\s*=\s*"([^"]*)"', text, re.M))
def config(ds): return json.load(open(glob.glob(f"{NRDS}/datastreams/{ds}/config/*.json")[0]))["short_range"]

def resources(ds, vpu, tf=None):
    """The VPU's entry in main.tf's vpu_resources: the defaults merged with its overrides, if any."""
    tf = re.sub(r"#.*", "", tf if tf is not None else open(f"{NRDS}/datastreams/{ds}/main.tf").read())
    block = r'\{((?:\s*\w+\s*=\s*"[^"]*")*)\s*\}'
    pairs = [m[1] for m in (re.search(rf"merge\({block}", tf), re.search(rf'"{vpu}"\s*=\s*{block}', tf)) if m]
    r = dict(re.findall(r'(\w+)\s*=\s*"([^"]*)"', "".join(pairs)))
    return {f"{k}_s3_uri": f"s3://{BUCKET}/" + p.replace("${vpu}", vpu) for k, p in r.items()}

def target(ds, vpu="", label="", path=""):  # a manual run names one; a pull request gets one per change
    return dict(key=f"{ds}_" + (os.path.basename(path)[:-4] or f"VPU_{vpu}"), datastream=ds, vpu=vpu, contribution=path,
                label=label or f"`{ds}` contribution `{os.path.basename(path)}`")

def targets(a):
    if a.contribution or a.datastream:
        found = [target(a.contribution.split("/")[-3], path=a.contribution)] if a.contribution else \
                [target(a.datastream, v.strip(), f"`{a.datastream}`") for v in a.vpus.split(",")]
    else:
        files, changed, found = sh("git", "diff", "--name-only", "--diff-filter=d", f"{a.base}...HEAD").split(), {}, []
        for f in files:
            if (m := WATCHED.match(f)) and m[1] in SUPPORTED and m[2] != "contributions":
                changed.setdefault(m[1], []).append(f"`{os.path.basename(f)}`")
            elif m and m[1] in SUPPORTED and f.endswith(".yml"):
                found.append(target(m[1], path=f))
        old, new = tfvars(sh("git", "show", f"{a.base}:{TFVARS}")), tfvars(open(TFVARS).read())
        for ds in SUPPORTED if TFVARS in files else []:  # a new AMI for a datastream
            if (k := f"{ds.replace('-', '_')}_ami_id") and old.get(k) != new.get(k):
                changed.setdefault(ds, []).append(f"AMI `{old.get(k)}` → `{new.get(k)}`")
        for ds in SUPPORTED:  # a VPU's geopackage or BMI configs
            if (p := f"{NRDS}/datastreams/{ds}/main.tf") in files and (tf := sh("git", "show", f"{a.base}:{p}")):
                found += [target(ds, v, f"`{ds}` VPU {v} resources") for v in config(ds)["instance_types"]
                          if (r := resources(ds, v, tf)) and r != resources(ds, v)]
        found[:0] = [target(ds, next(iter(config(ds)["instance_types"])), f"`{ds}` " + ", ".join(fs))
                     for ds, fs in changed.items()]
        found = [t for i, t in enumerate(found) if t["key"] not in {u["key"] for u in found[:i]}]
    print(json.dumps(found))

def render(ds, vpu, tv, init="00"):
    """The template filled in as schedules.tf fills it: a pinned nprocs, else the instance's vCPUs - 1,
    the init (short_range restarts from its own init) and the VPU's resources from main.tf."""
    cfg, tf = config(ds), open(f"{NRDS}/datastreams/{ds}/schedules.tf").read()
    itype = cfg["instance_types"][vpu]
    nprocs = (m := re.search(r"nprocs\s*=\s*(\d+)", tf)) and m[1] or int(re.search(rf'"{itype}" *= *(\d+)', tf)[1]) - 1
    v = {**SHORT_RANGE, "init": init, "restart_init": init, "vpu": vpu, "nprocs": nprocs, "instance_type": itype, "volume_size": cfg["volume_size"],
         "ami_id": tv[f"{ds.replace('-', '_')}_ami_id"], "instance_profile": tv["profile_name"], "s3_bucket": BUCKET,
         "environment_suffix": tv["environment_suffix"], **resources(ds, vpu)}
    tpl = open(glob.glob(f"{NRDS}/datastreams/{ds}/templates/*.tpl")[0]).read()
    # $${x} is templatefile's escape for a literal ${x}, a shell variable.
    return json.loads(re.sub(r"\$(\$?)\{(\w+)\}", lambda m: f"${{{m[2]}}}" if m[1] else str(v[m[2]]), tpl))

def run(a):
    date = a.date or (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y%m%d")  # default: yesterday
    init = a.init or SHORT_RANGE["init"]
    if not re.fullmatch(r"\d{8}", date) or init not in config(a.datastream)["init_cycles"]:
        sys.exit(f"date {date!r} must be YYYYMMDD and init {init!r} one of {a.datastream}'s short_range init_cycles")
    ex = render(a.datastream, a.vpu, tv := tfvars(open(TFVARS).read()), init)
    (cmd,) = ex["commands"]
    daily, live = re.search(r"--S3_PREFIX\s+([^\s']+)", cmd)[1], re.search(r" -R\s+([^\s']+)", cmd)[1]
    test = f"test/outputs_diff/{a.run_id}/{a.key}"
    # With -s DAILY, datastreamcli reads -e as the run date. The forcing is pinned too: with no DAILY in the
    # test prefix, streamcommander would fill the forcing's ngen.DAILY with the day the test runs.
    cmd = re.sub(r"(-F\s+\S*)ngen\.DAILY", rf"\1ngen.{date}", cmd.replace("-s DAILY", f"-s DAILY -e {date}0000"))
    cmd = re.sub(r"--S3_PREFIX\s+[^\s']+", f"--S3_PREFIX {test}", cmd)
    info = dict(vpu=a.vpu, date=date, init=init, prod_prefix=daily.replace("DAILY", date), test_prefix=test)
    if a.realization:  # a contribution runs its merged realization in place of the live one
        boto3.client("s3").upload_file(a.realization, BUCKET, cand := f"{test}/candidate/{os.path.basename(live)}")
        cmd, old = cmd.replace(live, f"s3://{BUCKET}/{cand}"), json.load(urllib.request.urlopen(live)).get("catchments", {})
        # The divides whose entries the contribution changes; troute reports cat-N's flowpath as feature_id N.
        info["features"] = [int(k[4:]) for k, v in json.load(open(a.realization))["catchments"].items() if v != old.get(k)]
    ex["commands"] = [cmd]
    ex["instance_parameters"]["TagSpecifications"][0]["Tags"][0]["Value"] = f"outputs_diff_{a.key}"  # the instance Name
    json.dump(info, open("run_info.json", "w"))
    sfn = boto3.client("stepfunctions")
    arn = sfn.start_execution(stateMachineArn=f"arn:aws:states:us-east-1:{ACCOUNT}:stateMachine:{tv['sm_name']}",
                              name=f"outputs-diff-{a.run_id}-{a.key}"[:80], input=json.dumps(ex))["executionArn"]
    while (status := sfn.describe_execution(executionArn=arn)["status"]) == "RUNNING":
        time.sleep(30)
    sys.exit(None if status == "SUCCEEDED" else f"{arn} ended {status}")

def uris(a): print("\n".join(f"{k}={u}" for k, u in resources(a.datastream, a.vpu).items()))

def compare(a):
    b, t = (pd.concat(map(pd.read_parquet, glob.glob(f"{d}/*.parquet"))) for d in ("baseline", "test"))
    m = b.merge(t, on=KEYS, how="outer", suffixes=("_b", "_t"))  # a row on one side only compares to NaN
    diff = {c: ~np.isclose(m[f"{c}_b"], m[f"{c}_t"], equal_nan=True) for c in b.columns if c not in KEYS}
    rows = np.logical_or.reduce(list(diff.values()))
    cols = ", ".join(f"`{c}` ({d.sum():,} rows)" for c, d in diff.items() if d.any())
    detail = f"{len(m):,} rows compared; " + (f"differs in {cols}" if cols else "all within tolerance")
    if "features" in (info := json.load(open("run_info.json"))):
        hit = m.loc[rows & m["feature_id"].isin(info["features"]), "feature_id"].nunique()
        detail += f"<br>{hit:,} of {len(info['features']):,} contributed catchments' flowpaths changed"
        detail += "" if hit else "<br>⚠️ **the contributed parameters did not change their catchments' outputs**"
    open("comment.md", "w").write(
        f"### Outputs diff: {a.label}\n\n| VPU | Baseline | Outputs | Detail |\n|---|---|---|---|\n"
        f"| {info['vpu']} | {info['date']} t{info['init']}z | {'🔀 Different' if rows.any() else '🟰 Same'} | {detail} |\n")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cmd", choices=["targets", "run", "compare", "uris"])
    for o in "base datastream vpus vpu contribution key label run-id date init realization".split():
        p.add_argument(f"--{o}", default="")
    a = p.parse_args()
    globals()[a.cmd](a)
