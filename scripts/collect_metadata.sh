#!/bin/bash

out_dir=""
input_date=""

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --out_dir)
            out_dir="$2"
            shift 2
            ;;
        --date)
            input_date="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$out_dir" ] || [ -z "$input_date" ]; then
    echo "Usage: $0 --out_dir <out_dir> --date <input_date>"
    exit 1
fi

if [ ! -d "$out_dir" ]; then
    mkdir -p "$out_dir" || { echo "Failed to create directory $out_dir"; exit 1; }
fi

VPUs=("01" "02" "03N" "03S" "03W" "04" "05" "06" "07" "08" "09" "10L" "10U" "11" "12" "13" "14" "15" "16" "17" "18")

for vpu in "${VPUs[@]}"; do
    profile_key="s3://ngen-datastream/daily/${input_date}/t4g.2xlarge_lite/VPU_${vpu}/datastream-metadata/profile.txt"
    conf_key="s3://ngen-datastream/daily/${input_date}/t4g.2xlarge_lite/VPU_${vpu}/datastream-metadata/conf_datastream.json"

    aws s3 cp "$profile_key" "$out_dir/profile_${vpu}.txt"
    aws s3 cp "$conf_key" "$out_dir/conf_datastream_${vpu}.json"
done
