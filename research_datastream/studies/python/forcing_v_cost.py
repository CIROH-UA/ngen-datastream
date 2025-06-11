import os
import sys
import argparse
import tempfile
from datetime import datetime, timedelta
import boto3
import xarray as xr
import pandas as pd
import matplotlib.pyplot as plt
import requests

BASE_URL = "https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2/ngen.{date}/short_range/{init:02d}/VPU_16/datastream-metadata/profile.txt"

def parse_profile_text(content):
    times = {}
    durations = {}

    # Extract all timestamp lines
    for line in content.strip().splitlines():
        if ":" in line:
            key, value = line.strip().split(":", 1)
            times[key.strip()] = value.strip()

    # Find all matching *_START and *_END pairs
    for key in times:
        if key.endswith("_START"):
            base = key[:-6]  # remove "_START"
            start_key = key
            end_key = base + "_END"
            if end_key in times:
                try:
                    start_time = datetime.strptime(times[start_key], "%Y%m%d%H%M%S")
                    end_time = datetime.strptime(times[end_key], "%Y%m%d%H%M%S")
                    duration = (end_time - start_time).total_seconds()
                    durations[base.lower()] = duration  # use lowercase step name
                except Exception as e:
                    print(f"Error parsing {base}: {e}")
    return durations

def collect_ngen_runtimes(start_date, end_date):
    current = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")
    records = []

    while current <= end:
        date_str = current.strftime("%Y%m%d")
        for init in range(24):
            url = BASE_URL.format(date=date_str, init=init)
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                durations = parse_profile_text(response.text)
                if durations:
                    record = {
                        "date": date_str,
                        "init": f"{init:02d}",
                        "timestamp": f"{date_str}T{init:02d}"
                    }
                    record.update(durations)  # Add step durations to the row
                    records.append(record)
                    print(f"Parsed durations from {date_str} {init:02d}Z: {durations}")
                else:
                    print(f"Missing step data in {date_str} {init:02d}Z")
            except Exception as e:
                print(f"Failed to retrieve {url}: {e}")
                records.append({
                    "date": date_str,
                    "init": f"{init:02d}",
                    "timestamp": f"{date_str}T{init:02d}"
                    # Don't add durations if the file couldn't be read
                })
        current += timedelta(days=1)

    return pd.DataFrame(records)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("start_date", help="Start date YYYYMMDD")
    parser.add_argument("end_date", help="End date YYYYMMDD")
    parser.add_argument("vpu", help="vpu")
    parser.add_argument("plot_var_forcings", help="Forcings ariable to plot (e.g., precip_rate_active_catchments)")
    parser.add_argument("plot_var_profiling", help="Profiling variable to plot (e.g., precip_rate_active_catchments)")
    return parser.parse_args()

def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(n)

def download_netcdf(url, dest):
    r = requests.get(url)
    if r.status_code == 200:
        with open(dest, 'wb') as f:
            f.write(r.content)
        return True
    return False

def summarize_dataset(file_path):
    try:
        ds = xr.open_dataset(file_path)
        summary = {}
        for var in ds.data_vars:
            if not pd.api.types.is_numeric_dtype(ds[var].dtype):
                continue  # Skip non-numeric variables like 'ids'
            values = ds[var].values.flatten()
            values = values[~pd.isnull(values)]
            if values.size > 0:
                summary[f"{var}_mean"] = values.mean()
                summary[f"{var}_median"] = pd.Series(values).median()
            else:
                summary[f"{var}_mean"] = None
                summary[f"{var}_median"] = None

        # Additional metric: number of catchments with any precip_rate > 0
        if "precip_rate" in ds.data_vars:
            pr = ds["precip_rate"]
            if "catchment-id" in pr.dims and "time" in pr.dims:
                # Check for each catchment if any value in time is > 0
                catchments_with_rain = (pr > 0).any(dim="time")
                summary["precip_rate_active_catchments"] = int(catchments_with_rain.sum().item())
            else:
                summary["precip_rate_active_catchments"] = None
        else:
            summary["precip_rate_active_catchments"] = None

        ds.close()
        return summary
    except Exception as e:
        print(f"Failed to process {file_path}: {e}")
        return {}

def get_cost_explorer_data(start, end):
    ce = boto3.client("ce")
    results = []

    # Convert from YYYYMMDD to YYYY-MM-DD
    start_date = datetime.strptime(start, "%Y%m%d").strftime("%Y-%m-%d")
    end_date = datetime.strptime(end, "%Y%m%d").strftime("%Y-%m-%d")

    next_token = None
    while True:
        kwargs = {
            "TimePeriod": {"Start": start_date, "End": end_date},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
            "GroupBy": [{"Type": "TAG", "Key": "Project"}],
        }
        if next_token:
            kwargs["NextPageToken"] = next_token

        response = ce.get_cost_and_usage(**kwargs)

        for group in response.get("ResultsByTime", []):
            time = group["TimePeriod"]["Start"]
            for g in group["Groups"]:
                if g["Keys"] == ["Project$datastream_short_range_16"]:
                    amount = float(g["Metrics"]["UnblendedCost"]["Amount"])
                    results.append({"timestamp": time, "cost": amount})

        next_token = response.get("NextPageToken")
        if not next_token:
            break

    return pd.DataFrame(results)


def main():
    args = parse_args()
    start_date = datetime.strptime(args.start_date, "%Y%m%d")
    end_date = datetime.strptime(args.end_date, "%Y%m%d")
    VPU = args.vpu
    plot_var_forcings = args.plot_var_forcings
    plot_var_profiling = args.plot_var_profiling

    forcing_data = []
    temp_dir = tempfile.mkdtemp()

    forcing_stats_file = f"forcing_stats_VPU_{VPU}_{args.start_date}_{args.end_date}.csv"
    if not os.path.exists(forcing_stats_file):
        print(f"Creating {forcing_stats_file}...")

        for dt in daterange(start_date, end_date):
            ymd = dt.strftime("%Y%m%d")
            for hour in range(24):
                cycle = f"{hour:02d}"
                url = f"https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2/ngen.{ymd}/forcing_short_range/{cycle}/ngen.t{cycle}z.short_range.forcing.f001_f018.VPU_16.nc"
                local_file = os.path.join(temp_dir, f"{ymd}_{cycle}.nc")

                print(f"Downloading {url}...")
                if download_netcdf(url, local_file):
                    print(f"  Processing {local_file}...")
                    stats = summarize_dataset(local_file)
                    stats.update({"timestamp": f"{ymd}T{cycle}"})
                    forcing_data.append(stats)

        forcing_df = pd.DataFrame(forcing_data)
        forcing_df.to_csv(f"forcing_stats_{args.start_date}_{args.end_date}.csv", index=False)
        print("Saved forcing_stats.csv")
    else:
        print(f"Loading existing {forcing_stats_file}...")
        forcing_df = pd.read_csv(forcing_stats_file)

    profiling_stats_file = f"profiling_stats_VPU_{VPU}_{args.start_date}_{args.end_date}.csv"
    if not os.path.exists(profiling_stats_file):
        profiling_df = collect_ngen_runtimes(args.start_date, args.end_date)
        profiling_df.to_csv(profiling_stats_file, index=False)
    else:
        print(f"Loading existing {profiling_stats_file}...")
        profiling_df = pd.read_csv(profiling_stats_file)

    # Merge and plot
    forcing_df["timestamp"] = pd.to_datetime(forcing_df["timestamp"], format="%Y%m%dT%H")
    profiling_df["timestamp"] = pd.to_datetime(profiling_df["timestamp"])

    VPU = 16

    print(f"Plotting timestamp vs. {plot_var_forcings}...")
    plt.figure(figsize=(10, 6))
    plt.scatter(forcing_df["timestamp"], forcing_df[plot_var_forcings], alpha=0.7)
    plt.xlabel("timestamp")
    plt.ylabel(f"{plot_var_forcings}")
    plt.title(f"VPU {VPU} timestamp v {plot_var_forcings}")
    plt.grid(True)
    plt.savefig(f"VPU_{VPU}_{args.start_date}_{args.end_date}_{plot_var_forcings}.png")
    # plt.show()

    print(f"Plotting timestamp vs. {plot_var_profiling}...")
    plt.figure(figsize=(10, 6))
    plt.scatter(profiling_df["timestamp"], profiling_df[plot_var_profiling], alpha=0.7)
    plt.xlabel("timestamp")
    plt.ylabel(plot_var_profiling)
    plt.ylim(200,300)
    plt.title(f"VPU {VPU} timestamp v {plot_var_profiling}")
    plt.grid(True)
    plt.savefig(f"VPU_{VPU}_{args.start_date}_{args.end_date}_{plot_var_profiling}.png")
    # plt.show()    

if __name__ == "__main__":
    main()
