#!/bin/bash

out_dir=""
prefix=""

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --out_dir)
            out_dir="$2"
            shift 2
            ;;
        --prefix)
            prefix="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$out_dir" ] || [ -z "$prefix" ]; then
    echo "Usage: $0 --out_dir <out_dir> --prefix <s3 prefix>"
    exit 1
fi

if [ ! -d "$out_dir" ]; then
    mkdir -p "$out_dir" || { echo "Failed to create directory $out_dir"; exit 1; }
fi

VPUs=("01" "02" "03N" "03S" "03W" "04" "05" "06" "07" "08" "09" "10L" "10U" "11" "12" "13" "14" "15" "16" "17" "18")

for vpu in "${VPUs[@]}"; do
    # prefix=s3://ngen-datastream/AWI_201903110100_202001010000
    profile_key=$prefix"/VPU_${vpu}/datastream-metadata/profile.txt"
    conf_key=$prefix"/VPU_${vpu}/datastream-metadata/conf_datastream.json"

    aws s3 cp "$profile_key" "$out_dir/profile_${vpu}.txt"
    aws s3 cp "$conf_key" "$out_dir/conf_datastream_${vpu}.json"
done