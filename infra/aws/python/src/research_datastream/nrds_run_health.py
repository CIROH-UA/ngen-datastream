#!/usr/bin/env python3
import argparse
import datetime
from datetime import timezone
import requests
import pandas as pd
import matplotlib.pyplot as plt
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import boto3
from urllib.parse import urlparse
import seaborn as sns
s3 = boto3.client("s3")

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

def get_lead_time_minutes(exec_url, end_time):
    """
    Calculate the lead time (lead_time_nwm) of the forecast by taking the difference
    between the end time and the time that the nwm forcing files were created.

    Also calculate the lead time (lead_time_ngen_minutes) of the forecast by taking the difference
    between the end time and the time that the ngen forcing files were created.

    """

    lead_time_ngen_minutes = None
    lead_time_nwm_minutes = None

    conf_fp = exec_url.replace("execution.json", "conf_fp.json")
    r = requests.get(conf_fp, timeout=10)
    if r.status_code == 200:
        data = r.json()
        forcing_url = data.get("forcing")
        parsed = urlparse(forcing_url, allow_fragments=False)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        response = s3.head_object(Bucket=bucket, Key=key)
        ngen_forcing_end_time = response['LastModified']   
        lead_time_ngen_minutes = end_time - ngen_forcing_end_time 
    else:
        print(f"Could not fetch conf_fp.json, status={r.status_code}")

    base_prefix = "/".join(key.split("/")[:-1])
    nwm_forcing_url = f"s3://{bucket}/{base_prefix}/metadata/forcings_metadata/filenamelist.txt"
    parsed = urlparse(nwm_forcing_url, allow_fragments=False)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    nwm_file = s3.get_object(Bucket=bucket, Key=key)['Body'].read().decode('utf-8').strip().splitlines()[-1]
    parsed = urlparse(nwm_file, allow_fragments=False)
    bucket = parsed.netloc.split(".")[0] 
    key = parsed.path.lstrip("/")
    response = s3.head_object(Bucket=bucket, Key=key)
    nwm_forcing_end_time = response['LastModified'].astimezone(timezone.utc)
    lead_time_nwm_minutes = end_time - nwm_forcing_end_time

    out = (lead_time_nwm_minutes.total_seconds() / 60, lead_time_ngen_minutes.total_seconds() / 60, nwm_forcing_end_time, ngen_forcing_end_time)

    return out


def fetch_execution_times(exec_json_url, run_url):
    """
    Fetch start_time from execution.json and end_time from run_url headers.
    """
    start_time = None
    end_time = None
    execution_time_minutes = None

    # Fetch execution.json start time
    try:
        r = requests.get(exec_json_url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            # Adjust the key based on your JSON structure
            start_time_str = data.get("t0")
            if start_time_str:
                start_time = datetime.datetime.fromtimestamp(start_time_str, tz=timezone.utc)
                print(f"Start time from execution.json: {start_time}")
            else:
                print(f"No start_time in {exec_json_url}")
        else:
            print(f"Could not fetch execution.json, status={r.status_code}")
    except Exception as e:
        print(f"Error fetching execution.json: {e}")

    # Fetch run file Last-Modified
    try:
        r = requests.head(run_url, timeout=10)
        if r.status_code == 200:
            last_modified = r.headers.get("Last-Modified")
            if last_modified:
                end_time = datetime.datetime.strptime(last_modified, "%a, %d %b %Y %H:%M:%S %Z")
                # convert to UTC if needed
                end_time = end_time.replace(tzinfo=datetime.timezone.utc)
                print(f"End time from run file headers: {end_time}")
            else:
                print(f"No Last-Modified header for {run_url}")
        else:
            print(f"Could not fetch run file headers, status={r.status_code}")
    except Exception as e:
        print(f"Error fetching run file headers: {e}")

    # Calculate lead time
    if start_time and end_time:
        execution_time_minutes = (end_time - start_time).total_seconds() / 60
        print(f"Execution time (minutes): {execution_time_minutes:.2f}")
    else:
        print(f"Could not calculate lead time for {run_url}")

    return start_time, end_time, execution_time_minutes

def process_run(date_str, run_type, hour, vpu, ens, cached_urls, df_cache):
    if run_type == "medium_range":
        run_url = f"{BASE_URL}/ngen.{date_str}/{run_type}/{hour}/{ens}/VPU_{vpu}/ngen-run.tar.gz"
        exec_json_url = f"{BASE_URL}/ngen.{date_str}/{run_type}/{hour}/{ens}/VPU_{vpu}/datastream-metadata/execution.json"
    else:
        run_url = f"{BASE_URL}/ngen.{date_str}/{run_type}/{hour}/VPU_{vpu}/ngen-run.tar.gz"
        exec_json_url = f"{BASE_URL}/ngen.{date_str}/{run_type}/{hour}/VPU_{vpu}/datastream-metadata/execution.json"

    print(f"Processing run: {run_url}")

    if run_url in cached_urls:
        row = df_cache[df_cache["run_url"] == run_url].iloc[0].to_dict()
        print(f"Using cached {run_url}")
        return row

    status = check_url(run_url)
    retry, retries_allowed = fetch_execution_metadata(exec_json_url)

    print(f"Checked run URL: status={status}, retry={retry}, retries_allowed={retries_allowed}")

    start_time, end_time, execution_time_minutes = fetch_execution_times(exec_json_url, run_url)
    print(f"Execution time: start_time={start_time}, end_time={end_time}, execution_time_minutes={execution_time_minutes}")

    (lead_time_nwm_minutes, lead_time_ngen_minutes, nwm_end_time, ngen_end_time) = get_lead_time_minutes(exec_json_url,end_time)
    print(f"Lead times: NWM={lead_time_nwm_minutes}, NGEN={lead_time_ngen_minutes}")

    return {
        "date": date_str,
        "run_type": run_type,
        "init_cycle": hour,
        "ensemble": ens if run_type == "medium_range" else None,
        "vpu": vpu,
        "run_url": run_url,
        "status_code": status,
        "status": "success" if status == 200 else "failure",
        "retry_attempt": retry,
        "retries_allowed": retries_allowed,
        "execution_t0": start_time,
        "output_time": end_time,
        "execution_time_minutes": execution_time_minutes,
        "nwm_forcing_end_time": nwm_end_time,
        "ngen_forcing_end_time": ngen_end_time,
        "lead_time_nwm_minutes": lead_time_nwm_minutes,
        "lead_time_ngen_minutes": lead_time_ngen_minutes
    }

def plot_violin_group(df, output_file, title):
    group_cols = [
        ("date", "By Date"),
        ("retry_attempt", "By Retry Attempt"),
        ("vpu", "By VPU"),
        ("run_type", "By Run Type"),
        ("init_cycle", "By Init Cycle"),
        ("ensemble", "By Ensemble")
    ]

    n_plots = len(group_cols)
    n_cols = 2
    n_rows = (n_plots + 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, n_rows * 5))
    axes = axes.flatten()

    for ax, (group_col, subtitle) in zip(axes, group_cols):
        # Drop rows where the group column is NaN
        df_sub = df.dropna(subset=[group_col])
        if df_sub.empty:
            ax.set_title(f"{subtitle} (no data)")
            ax.axis("off")
            continue

        # Melt dataframe for Seaborn
        df_melted = df_sub.melt(
            id_vars=[group_col],
            value_vars=["execution_time_minutes", "lead_time_nwm_minutes", "lead_time_ngen_minutes"],
            var_name="Metric",
            value_name="Minutes"
        )
        df_melted["Metric"] = df_melted["Metric"].replace({
            "execution_time_minutes": "Execution Time",
            "lead_time_nwm_minutes": "Lead Time NWM",
            "lead_time_ngen_minutes": "Lead Time NGEN"
        })

        # plot boxplots
        sns.violinplot(
            x=group_col,
            y="Minutes",
            hue="Metric",
            data=df_melted,
            palette=["deepskyblue", "mediumseagreen", "orange"],
            split=False,
            inner="quartile",
            ax=ax
        )

        ax.set_title(subtitle, fontsize=12)
        ax.set_xlabel(group_col)
        ax.set_ylabel("Minutes")
        ax.tick_params(axis="x", rotation=45)
        ax.legend_.remove()  # remove per-subplot legend

    # Remove unused axes
    for i in range(len(group_cols), len(axes)):
        fig.delaxes(axes[i])

    # Single legend for the figure
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        ncol=3,
        fontsize=12,
        frameon=False
    )

    fig.suptitle(title, fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(output_file)
    plt.close()

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

import matplotlib.patches as mpatches

def plot_all_grouped_counts(df, output_file, title):
    group_cols = [
        ("date",         "By Date"),
        ("retry_attempt","By Retry Attempt"),
        ("vpu",          "By VPU"),
        ("run_type",     "By Run Type"),
        ("init_cycle",   "By Init Cycle"),
        ("ensemble",     "By Ensemble"),
    ]

    color_map = {
        "success": "limegreen",
        "failure": "darkred"
    }

    n_plots = len(group_cols)
    n_cols = 2
    n_rows = (n_plots + 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, n_rows*5))
    axes = axes.flatten()

    for ax, (group_col, subtitle) in zip(axes, group_cols):
        counts = df.groupby([group_col, "status"]).size().unstack(fill_value=0)
        # Ensure consistent column order
        for col in ["success", "failure"]:
            if col not in counts.columns:
                counts[col] = 0
        counts = counts[["success", "failure"]]

        if counts.empty:
            ax.set_title(f"{subtitle} (no data)")
            ax.axis("off")  # Hide empty plot
            continue        

        counts.plot(
            kind="bar",
            ax=ax,
            color=[color_map[col] for col in counts.columns],
            legend=False
        )

        ax.set_title(subtitle, fontsize=12)
        ax.set_xlabel(group_col)
        ax.set_ylabel("Count")
        ax.set_yscale("log")
        ax.tick_params(axis="x", rotation=45)

        for container in ax.containers:
            ax.bar_label(container, label_type="edge", fontsize=8)

    # Remove unused subplots
    for i in range(len(group_cols), len(axes)):
        fig.delaxes(axes[i])

    # Create a proper legend manually
    legend_handles = [mpatches.Patch(color=color_map[col], label=col) for col in ["success", "failure"]]
    fig.legend(
        handles=legend_handles,
        loc="upper center",
        ncol=2,
        fontsize=12,
        frameon=False
    )

    fig.suptitle(
        f"\n{title}"
        f"\nNRDS CFE NOM START\n",        
        fontsize=14, fontweight="bold"
    )

    plt.tight_layout(rect=[0, 0, 1, 0.92])
    plt.savefig(output_file)
    plt.close()

def plot_all_grouped_boxnwhisker(df, output_file, title):
    group_cols = [
        ("date",         "By Date"),
        ("retry_attempt","By Retry Attempt"),
        ("vpu",          "By VPU"),
        ("run_type",     "By Run Type"),
        ("init_cycle",   "By Init Cycle"),
        ("ensemble",     "By Ensemble"),
    ]

    color_map = {
        "execution_time_minutes": "green",
        "lead_time_nwm_minutes": "magenta",
        "lead_time_ngen_minutes": "blue"
    }

    n_plots = len(group_cols)
    n_cols = 2
    n_rows = (n_plots + 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, n_rows*5))
    axes = axes.flatten()

    for ax, (group_col, subtitle) in zip(axes, group_cols):
        vals = df.groupby([group_col, "execution_time_minutes"]).size().unstack(fill_value=0)

        if vals.empty:
            ax.set_title(f"{subtitle} (no data)")
            ax.axis("off")  # Hide empty plot
            continue        

        # counts.plot(
        #     kind="bar",
        #     ax=ax,
        #     color=[color_map[col] for col in counts.columns],
        #     legend=False
        # )

        vals.boxplot(by=group_col, ax=ax, color=color_map["execution_time_minutes"])
        # vals.boxplot("lead_time_nwm_minutes", by=group_col, ax=ax, color=color_map["lead_time_nwm_minutes"])
        # vals.boxplot("lead_time_ngen_minutes", by=group_col, ax=ax, color=color_map["lead_time_ngen_minutes"])
        #
        # 
        # vals.boxplot(by=group_col, ax=ax, color=[color_map[col] for col in vals.columns])

        ax.set_title(subtitle, fontsize=12)
        ax.set_xlabel(group_col)
        ax.set_ylabel("Count")
        ax.set_yscale("log")
        ax.tick_params(axis="x", rotation=45)

        for container in ax.containers:
            ax.bar_label(container, label_type="edge", fontsize=8)

    # Remove unused subplots
    for i in range(len(group_cols), len(axes)):
        fig.delaxes(axes[i])

    # Create a proper legend manually
    legend_handles = [mpatches.Patch(color=color_map[col], label=col) for col in ["success", "failure"]]
    fig.legend(
        handles=legend_handles,
        loc="upper center",
        ncol=2,
        fontsize=12,
        frameon=False
    )

    fig.suptitle(
        f"\n{title}"
        f"\nNRDS CFE NOM START {start_date} END {end_date}\n",        
        fontsize=14, fontweight="bold"
    )

    plt.tight_layout(rect=[0, 0, 1, 0.92])
    plt.savefig(output_file)
    plt.close()


def output_anomaly_csvs(df, output_dir):
    """
    Filter anomalies and output CSVs with times in minutes:
      - retries_gt0.csv
      - execution_time_anomalies.csv
      - lead_time_anomalies.csv
      - anomaly_free.csv

    Returns:
        df_anomaly_free: DataFrame containing only rows without any anomalies, in minutes.
    """
    os.makedirs(output_dir, exist_ok=True)

    exec_lim = 120
    lead_lim = 720

    df_retry = df[df['retry_attempt'] > 0]
    if not df_retry.empty:
        df_retry.to_csv(os.path.join(output_dir, "retries_gt0.csv"), index=False)
        print(f"Found {len(df_retry)} rows with retry_attempt > 0. Saved to retries_gt0.csv")

    df_exec_anomaly = df[(df['execution_time_minutes'] < 0) | (df['execution_time_minutes'] > exec_lim)]
    if not df_exec_anomaly.empty:
        df_exec_anomaly.to_csv(os.path.join(output_dir, "execution_time_anomalies.csv"), index=False)
        print(f"Found {len(df_exec_anomaly)} rows with abnormal execution_time_minutes. Saved to execution_time_anomalies.csv")

    df_lead_anomaly = df[
        (df['lead_time_nwm_minutes'] < 0) | (df['lead_time_nwm_minutes'] > lead_lim) |
        (df['lead_time_ngen_minutes'] < 0) | (df['lead_time_ngen_minutes'] > lead_lim)
    ]
    if not df_lead_anomaly.empty:
        df_lead_anomaly.to_csv(os.path.join(output_dir, "lead_time_anomalies.csv"), index=False)
        print(f"Found {len(df_lead_anomaly)} rows with abnormal lead times. Saved to lead_time_anomalies.csv")

    df_anomaly_free = df[
        (df['retry_attempt'] == 0) &
        (df['execution_time_minutes'] >= 0) & (df['execution_time_minutes'] <= exec_lim) &
        (df['lead_time_nwm_minutes'] >= 0) & (df['lead_time_nwm_minutes'] <= lead_lim) &
        (df['lead_time_ngen_minutes'] >= 0) & (df['lead_time_ngen_minutes'] <= lead_lim)
    ]
    df_anomaly_free.to_csv(os.path.join(output_dir, "anomaly_free.csv"), index=False)
    print(f"Saved {len(df_anomaly_free)} anomaly-free rows to anomaly_free.csv")

    return df_anomaly_free

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
    tasks = []   


    # Hardcoded debug call
    row = process_run(
        date_str="20250906",      # one date to test
        run_type="medium_range",    # run type to test
        hour="00",                 # init cycle
        vpu="02",                 # VPU
        ens=7,                  # ensemble (None for short_range)
        cached_urls=set(),         # no cache for debugging
        df_cache=pd.DataFrame()    # empty DataFrame for debugging
    )
    rows.append(row)
    print("DEBUG row output:", row)


    with ThreadPoolExecutor(max_workers=20) as executor:  # adjust worker count if needed
        for current_date in daterange(start_date, end_date):
            date_str = current_date.strftime("%Y%m%d")
            for run_type in run_types:
                allowed_hours = INIT_CYCLES_ALLOWED[run_type]
                hours_to_check = allowed_hours if custom_cycles is None else [h for h in custom_cycles if h in allowed_hours]
                for hour in hours_to_check:
                    for vpu in vpus:
                        if run_type == "medium_range":
                            for ens in ensembles:
                                tasks.append(
                                    executor.submit(process_run, date_str, run_type, hour, vpu, ens, cached_urls, df_cache)
                                )
                        else:
                            tasks.append(
                                executor.submit(process_run, date_str, run_type, hour, vpu, None, cached_urls, df_cache)
                            )

        for future in as_completed(tasks):
            row = future.result()
            rows.append(row)

    # Combine with cache and write CSV
    df_new = pd.DataFrame(rows)
    if not df_cache.empty:
        df_combined = pd.concat([df_cache, df_new]).drop_duplicates(subset="run_url", keep="first")
    else:
        df_combined = df_new

    csv_dir = os.path.dirname(args.csv)

    if not os.path.exists(csv_dir):
        os.makedirs(csv_dir, exist_ok=True)
    if not os.path.exists(args.csv):
        df_combined.to_csv(args.csv, index=False)
    print(f"Wrote {len(df_combined)} rows to {args.csv}")

    os.makedirs(args.charts_dir, exist_ok=True)
    plot_all_grouped_counts(
        df_combined,
        os.path.join(args.charts_dir, "success_failure_all.png"),
        "Success vs Failure Summary"
    )

    df_clean = output_anomaly_csvs(df_combined, args.charts_dir)

    for df, label in [
    (df_combined, "all_runs"),
    (df_clean, "clean_runs"),
    ]:
        plot_violin_group(
            df,
            os.path.join(args.charts_dir, f"{label}_violin.png"),
            f"{label.replace('_', ' ').upper()} Execution & Lead Time Distribution"
        )

    for df, label in [
    (df_combined, "all_runs"),
    (df_clean, "clean_runs"),
    ]:
        plot_all_grouped_boxnwhisker(
            df,
            os.path.join(args.charts_dir, f"{label}_violin.png"),
            f"{label.replace('_', ' ').upper()} Execution & Lead Time Distribution"
        )        

    print(f"Charts saved to {args.charts_dir}/")

if __name__ == "__main__":
    main()
