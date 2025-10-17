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

    vpu_areas = {'VPU_01': np.float64(169506.94567295208),
    'VPU_02': np.float64(277762.650207525),
    'VPU_03N': np.float64(251265.12994153082),
    'VPU_03S': np.float64(182296.01595399337),
    'VPU_03W': np.float64(242246.5998014469),
    'VPU_04': np.float64(324439.98450048204),
    'VPU_05': np.float64(421969.3497738968),
    'VPU_06': np.float64(105953.98609154101),
    'VPU_07': np.float64(492039.5078722859),
    'VPU_08': np.float64(285361.28012152814),
    'VPU_09': np.float64(213494.848377173),
    'VPU_10L': np.float64(540260.5528299824),
    'VPU_10U': np.float64(811320.0216991806),
    'VPU_11': np.float64(642313.8817198629),
    'VPU_12': np.float64(464411.5282732017),
    'VPU_13': np.float64(564896.7216874297),
    'VPU_14': np.float64(293580.3838511146),
    'VPU_15': np.float64(366915.49905261456),
    'VPU_16': np.float64(367296.8106658667),
    'VPU_17': np.float64(814521.4465534835),
    'VPU_18': np.float64(422084.5544481264)}

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

            duration = (profile[end_key] - profile[start_key]).seconds
            if durations.get(step) is None:
                durations[step] = np.array([])
            durations[step] = np.append(durations[step], duration)

        # normed data
        for step in steps:
            if durations_normed.get(step) is None:
                durations_normed[step] = np.array([])
            durations_normed[step] = np.append(durations_normed[step],
                                               durations[step][-1] / vpu_areas[vpu])

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

    ax.set_title(f"VPU Performance Comparison for {runtype} {date} {time}z Normalized by VPU Area")
    ax.set_ylabel("Duration (s/km^2)")
    ax.set_xlabel("VPUs")
    ax.legend()
    fig.set_figwidth(20)
    fig.set_figheight(10)
    plt.savefig(f"vpu_comparison_normed_{date}_{runtype}_{time}.png")


if __name__ == "__main__":
    main()