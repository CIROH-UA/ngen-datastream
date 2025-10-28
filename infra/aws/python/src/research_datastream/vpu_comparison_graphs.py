"""
Generates datastream VPU performance comparison graphs from profile metadata files
for a specified date, run type, and time.

Usage:
    python3 vpu_comparison_graphs.py -d YYYYMMDD -r runtype -t time
    example:
        python3 vpu_comparison_graphs.py -d 20251009 -r short_range -t 14

Run type options:
    analysis_assim_extend
    medium_range
    short_range

Written by Quinn Lee, qylee@ua.edu
"""

from s3fs import S3FileSystem
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--date", type=str, required=True, help="Date in YYYYMMDD format")
    parser.add_argument("-r", "--runtype", type=str, required=True, 
                        choices=['analysis_assim_extend', 'medium_range', 'short_range'], 
                        help="Run type")
    parser.add_argument("-t", "--time", type=str, required=True, help="Time (e.g., 00, 06, 12, 18)")
    args = parser.parse_args()
    date = args.date
    runtype = args.runtype 
    time = args.time

    vpu_num_cats = {'VPU_01': 20567,
    'VPU_02': 35494,
    'VPU_03N': 31326,
    'VPU_03S': 30844,
    'VPU_03W': 14138,
    'VPU_04': 36312,
    'VPU_05': 51582,
    'VPU_06': 14167,
    'VPU_07': 57595,
    'VPU_08': 32993,
    'VPU_09': 11204,
    'VPU_10L': 55050,
    'VPU_10U': 84376,
    'VPU_11': 63177,
    'VPU_12': 36611,
    'VPU_13': 25471,
    'VPU_14': 32977,
    'VPU_15': 39696,
    'VPU_16': 34401,
    'VPU_17': 81841,
    'VPU_18': 41955}

    s3 = S3FileSystem(anon=True)
    url = f"s3://ciroh-community-ngen-datastream/v2.2/ngen.{date}/{runtype}/{time}/"
    try:
        vpu_urls = sorted(s3.ls(url))
    except FileNotFoundError:
        print(f"No data found for the specified parameters: {url}")
        return
    vpus = [vpu_url.split("/")[-1] for vpu_url in vpu_urls]

    # collect data for graphs
    durations = {}
    durations_normed = {}
    for url in vpu_urls:
        vpu = url.split("/")[-1]
        with s3.open(f"{url}/datastream-metadata/profile.txt", "r") as raw_profile:
            lines = raw_profile.readlines()
            profile = {}
            for line in lines:
                cleaned_line = line.strip().split(": ")
                profile[cleaned_line[0]] = datetime.strptime(cleaned_line[1], "%Y%m%d%H%M%S")
        steps = []
        for key in list(profile.keys()):
            if key == "DATASTREAM_START" or key == "DATASTREAM_END":
                continue
            if "_START" in key:
                step = key.replace("_START", "")
                steps.append(step)
            else:
                step = key.replace("_END", "")
                if step not in steps:
                    steps.append(step)
        
        # unnormed data
        for step in steps:
            start_key = f"{step}_START"
            end_key = f"{step}_END"

            duration = (profile[end_key] - profile[start_key]).total_seconds()
            if durations.get(step) is None:
                durations[step] = np.array([])
            durations[step] = np.append(durations[step], duration)

        # normed data
        for step in steps:
            if durations_normed.get(step) is None:
                durations_normed[step] = np.array([])
            durations_normed[step] = np.append(durations_normed[step],
                                               durations[step][-1] / vpu_num_cats[vpu])

    # unnormed graph
    fig, ax = plt.subplots()
    bottom = np.zeros(len(vpus))

    for step, length in durations.items():
        ax.bar(vpus, length, bottom=bottom, label=step)
        bottom += length

    ax.set_title(f"VPU Performance Comparison for {runtype} {date} {time}z")
    ax.set_ylabel("Duration (s)")
    ax.set_xlabel("VPUs")
    ax.legend()
    fig.set_figwidth(20)
    fig.set_figheight(10)

    plt.savefig(f"vpu_comparison_{date}_{runtype}_{time}z.png")  

    # normed graph
    fig, ax = plt.subplots()
    bottom = np.zeros(len(vpus))

    for step, length in durations_normed.items():
        ax.bar(vpus, length, bottom=bottom, label=step)
        bottom += length

    ax.set_title(f"VPU Performance Comparison for {runtype} {date} {time}z Normalized by Number of Catchments")
    ax.set_ylabel("Duration (s/# catchments)")
    ax.set_xlabel("VPUs")
    ax.legend()
    fig.set_figwidth(20)
    fig.set_figheight(10)
    plt.savefig(f"vpu_comparison_normed_{date}_{runtype}_{time}.png")


if __name__ == "__main__":
    main()