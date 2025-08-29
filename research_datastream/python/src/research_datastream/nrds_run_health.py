#!/usr/bin/env python3
import argparse
import csv
import datetime
import requests
import pandas as pd
import matplotlib.pyplot as plt
import os

plt.style.use('dark_background')

BASE_URL = "https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2"

# Allowed init cycles
INIT_CYCLES_ALLOWED = {
    "short_range": [f"{i:02d}" for i in range(24)],
    "medium_range": ["00", "06", "12", "18"],
    "analysis_assim_extend": ["16"]
}

# Default VPU list
ALL_VPUS = ["01", "02", "03N", "03S", "03W", "04", "05", "06", "07", "08",
            "09", "10U", "10L", "11", "12", "13", "14", "15", "16", "17", "18"]

ALL_ENSEMBLES = ["1", "2", "3", "4", "5", "6", "7"]

def daterange(start_date: datetime.date, end_date: datetime.date):
    for n in range((end_date - start_date).days + 1):
        yield start_date + datetime.timedelta(n)

def check_url(url: str) -> int:
    try:
        r = requests.head(url, timeout=10)
        return r.status_code
    except Exception:
        return 0

def fetch_execution_metadata(url: str):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            retry = data.get("retry_attempt")
            retries_allowed = data.get("run_options", {}).get("n_retries_allowed")
            return retry, retries_allowed
    except Exception:
        pass
    return None, None

def plot_all_grouped_counts(df, output_file, title, start_date, end_date, custom_cycles, vpus, run_types, ensembles):
    group_cols = [
        ("vpu",        f"By VPU"),
        ("run_type",   f"By Run Type"),
        ("init_cycle", f"By Init Cycle"),
        ("ensemble",   f"By Ensemble"),
    ]

    color_map = {
        "success": "limegreen",   # vibrant green
        "failure": "darkred"      # deep red
    }

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))  # 2x2 grid
    axes = axes.flatten()

    for ax, (group_col, subtitle) in zip(axes, group_cols):
        counts = df.groupby([group_col, "status"]).size().unstack(fill_value=0)
        if "success" in counts.columns and "failure" in counts.columns:
            counts = counts[["success", "failure"]]

        counts.plot(
            kind="bar",
            ax=ax,
            color=[color_map.get(col, "gray") for col in counts.columns]
        )

        ax.set_title(subtitle, fontsize=12)
        ax.set_xlabel(group_col)
        ax.set_ylabel("Count")
        ax.set_yscale("log")
        ax.tick_params(axis="x", rotation=45)

        # Annotate bars
        for container in ax.containers:
            ax.bar_label(container, label_type="edge", fontsize=8)

    # Big overall title
    fig.suptitle(
        f"NRDS START {start_date} END {end_date}\n"
        f"INITs: {custom_cycles}\nVPUs: {vpus}\nRUN TYPES: {run_types}\nEnsembles: {ensembles}\n\n"
        "Success vs Failure Across VPU, Run Type, Init Cycle, Ensemble",
        fontsize=14, fontweight="bold"
    )

    plt.tight_layout(rect=[0, 0, 1, 0.95])  # leave space for the suptitle
    plt.savefig(output_file)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Check datastream outputs and record results in CSV with charts.")
    parser.add_argument("--start", required=True, help="Start date YYYYMMDD")
    parser.add_argument("--end", required=True, help="End date YYYYMMDD")
    parser.add_argument("--vpus", default="16", help="Comma-separated VPUs or 'all'")
    parser.add_argument("--run_types", default="all", help="Comma-separated run types or 'all'")
    parser.add_argument("--init_cycles", default="all", help="Comma-separated init cycles or 'all'")
    parser.add_argument("--ensembles", default="all", help="Comma-separated ensembles or 'all' (medium_range only)")
    parser.add_argument("--csv", default="datastream_results.csv", help="Output CSV file")
    parser.add_argument("--charts_dir", default="charts", help="Directory to save charts")

    args = parser.parse_args()

    start_date = datetime.datetime.strptime(args.start, "%Y%m%d").date()
    end_date = datetime.datetime.strptime(args.end, "%Y%m%d").date()

    vpus = ALL_VPUS if args.vpus == "all" else args.vpus.split(",")
    run_types = ["short_range", "medium_range", "analysis_assim_extend"] if args.run_types == "all" else args.run_types.split(",")
    ensembles = ALL_ENSEMBLES if args.ensembles == "all" else args.ensembles.split(",")
    custom_cycles = None if args.init_cycles == "all" else [f"{int(x):02d}" for x in args.init_cycles.split(",")]

    # Load cache CSV if exists
    if os.path.exists(args.csv):
        df_cache = pd.read_csv(args.csv)
        cached_urls = set(df_cache["run_url"].tolist())
        print(f"Loaded {len(cached_urls)} cached URLs from {args.csv}")
    else:
        df_cache = pd.DataFrame()
        cached_urls = set()

    rows = []

    for current_date in daterange(start_date, end_date):
        date_str = current_date.strftime("%Y%m%d")

        for run_type in run_types:
            allowed_hours = INIT_CYCLES_ALLOWED[run_type]
            hours_to_check = allowed_hours if custom_cycles is None else [h for h in custom_cycles if h in allowed_hours]

            for hour in hours_to_check:
                for vpu in vpus:
                    if run_type == "medium_range":
                        for ens in ensembles:
                            run_url = f"{BASE_URL}/ngen.{date_str}/{run_type}/{hour}/{ens}/VPU_{vpu}/ngen-run.tar.gz"
                            exec_url = f"{BASE_URL}/ngen.{date_str}/{run_type}/{hour}/{ens}/VPU_{vpu}/datastream-metadata/execution.json"

                            if run_url in cached_urls:
                                row = df_cache[df_cache["run_url"] == run_url].iloc[0].to_dict()
                                print(f"Using cached {run_url}")
                            else:
                                status = check_url(run_url)
                                retry, retries_allowed = fetch_execution_metadata(exec_url)
                                print(f"Checked {run_url}: status {status}, retry {retry}, allowed {retries_allowed}")
                                row = {
                                    "date": date_str,
                                    "run_type": run_type,
                                    "init_cycle": hour,
                                    "ensemble": ens,
                                    "vpu": vpu,
                                    "run_url": run_url,
                                    "status_code": status,
                                    "status": "success" if status == 200 else "failure",
                                    "retry_attempt": retry,
                                    "retries_allowed": retries_allowed
                                }
                            rows.append(row)
                    else:
                        run_url = f"{BASE_URL}/ngen.{date_str}/{run_type}/{hour}/VPU_{vpu}/ngen-run.tar.gz"
                        exec_url = f"{BASE_URL}/ngen.{date_str}/{run_type}/{hour}/VPU_{vpu}/datastream-metadata/execution.json"

                        if run_url in cached_urls:
                            row = df_cache[df_cache["run_url"] == run_url].iloc[0].to_dict()
                            print(f"Using cached {run_url}")
                        else:
                            status = check_url(run_url)
                            retry, retries_allowed = fetch_execution_metadata(exec_url)
                            print(f"Checked {run_url}: status {status}, retry {retry}, allowed {retries_allowed}")
                            row = {
                                "date": date_str,
                                "run_type": run_type,
                                "init_cycle": hour,
                                "ensemble": None,
                                "vpu": vpu,
                                "run_url": run_url,
                                "status_code": status,
                                "status": "success" if status == 200 else "failure",
                                "retry_attempt": retry,
                                "retries_allowed": retries_allowed
                            }
                        rows.append(row)

    # Combine with cache and write CSV
    df_new = pd.DataFrame(rows)
    if not df_cache.empty:
        df_combined = pd.concat([df_cache, df_new]).drop_duplicates(subset="run_url", keep="first")
    else:
        df_combined = df_new

    if not os.path.exists(os.path.dirname(args.csv)):
        os.makedirs(os.path.dirname(args.csv), exist_ok=True)
    if not os.path.exists(args.csv):
        df_combined.to_csv(args.csv, index=False)
    print(f"Wrote {len(df_combined)} rows to {args.csv}")

    ii_n_retry_g_0 = any(df_combined['retry_attempt'] >= 1)
    if ii_n_retry_g_0:
        print("Runs with retry_attempt >= 1:")
        print(df_combined[df_combined['retry_attempt'] >= 1])

    os.makedirs(args.charts_dir, exist_ok=True)
    plot_all_grouped_counts(
        df_combined,
        os.path.join(args.charts_dir, "success_failure_all.png"),
        "Success vs Failure Summary",
        start_date,
        end_date,
        custom_cycles,
        vpus,
        run_types,
        ensembles
    )

    print(f"Charts saved to {args.charts_dir}/")

if __name__ == "__main__":
    main()
