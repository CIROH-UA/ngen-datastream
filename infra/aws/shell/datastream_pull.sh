#!/bin/bash

# Usage: ./datastream_pull <type> <dates> <range> <cycles> <vpus> [<output_dir>] [<version>]
# Type: metadata, forcing, output, merkdir, resources, forcing_metadata, all
# Dates: comma-separated, e.g., 20250701,20250702 or - for resources
# Range: short_range or - for resources
# Cycles: comma-separated, e.g., 00,01 or - for resources
# VPUs: comma-separated, e.g., VPU_12,VPU_16 or - for forcing_metadata
# output_dir: optional, default is current directory
# version: optional, default is v2.2
# Example for forcing_metadata: ./datastream_pull forcing_metadata 20250701 short_range 00 - ./data v2.2

type=$1
dates=$2
range=$3
cycles=$4
vpus=$5
output_dir=${6:-.}
version=${7:-v2.2}

base_url="https://ciroh-community-ngen-datastream.s3.amazonaws.com"

# Validate inputs
if [[ -z "$type" || -z "$dates" || -z "$range" || -z "$cycles" || -z "$vpus" ]]; then
    echo "Error: All arguments (type, dates, range, cycles, vpus) must be provided."
    echo "Usage: $0 <type> <dates> <range> <cycles> <vpus> [<output_dir>] [<version>]"
    exit 1
fi

if [[ "$type" == "resources" ]]; then
    subpath="${version}_resources"
else
    subpath="$range"
    if [[ "$type" == "forcing" || "$type" == "forcing_metadata" ]]; then
        subpath="forcing_$range"
    fi
fi

metadata_files=("conf_datastream.json" "conf_fp.json" "conf_nwmurl.json" "datastream.env" "datastream_steps.txt" "docker_hashes.txt" "profile.txt" "realization_datastream.json" "realization_user.json")

IFS=',' read -r -a date_array <<< "$dates"
IFS=',' read -r -a cycle_array <<< "$cycles"
IFS=',' read -r -a vpu_array <<< "$vpus"

function download_metadata() {
    local date=$1
    local cycle=$2
    local vpu=$3
    local dir_path="${version}/ngen.${date}/${range}/${cycle}/${vpu}/datastream-metadata"
    local local_dir="${output_dir}/${dir_path}"
    mkdir -p "$local_dir"
    for file in "${metadata_files[@]}"; do
        url="${base_url}/${dir_path}/${file}"
        echo "Attempting to download: $url"
        curl -f -s -o "${local_dir}/${file}" "$url" || echo "Failed to download $url"
    done
}

function download_forcing() {
    local date=$1
    local cycle=$2
    local vpu=$3
    local dir_path="${version}/ngen.${date}/forcing_${range}/${cycle}"
    local local_dir="${output_dir}/${dir_path}"
    mkdir -p "$local_dir"
    local file="ngen.t${cycle}z.${range}.forcing.f001_f018.${vpu}.nc"
    url="${base_url}/${dir_path}/${file}"
    echo "Attempting to download: $url"
    curl -f -s -o "${local_dir}/${file}" "$url" || echo "Failed to download $url"
}

function download_merkdir() {
    local date=$1
    local cycle=$2
    local vpu=$3
    local dir_path="${version}/ngen.${date}/${range}/${cycle}/${vpu}"
    local local_dir="${output_dir}/${dir_path}"
    mkdir -p "$local_dir"
    local file="merkdir.file"
    url="${base_url}/${dir_path}/${file}"
    echo "Attempting to download: $url"
    curl -f -s -o "${local_dir}/${file}" "$url" || echo "Failed to download $url"
}

function download_output() {
    local date=$1
    local cycle=$2
    local vpu=$3
    local dir_path="${version}/ngen.${date}/${range}/${cycle}/${vpu}"
    local local_dir="${output_dir}/${dir_path}"
    mkdir -p "$local_dir"
    local file="ngen-run.tar.gz"
    url="${base_url}/${dir_path}/${file}"
    echo "Attempting to download: $url"
    curl -f -s -o "${local_dir}/${file}" "$url" || echo "Failed to download $url"
}

function download_resources() {
    local vpu=$1
    local dir_path="${version}_resources/${vpu}"
    local local_dir="${output_dir}/${dir_path}"
    mkdir -p "$local_dir"
    listing_url="${base_url}/?prefix=${dir_path}/&delimiter=/"
    echo "Fetching listing: $listing_url"
    xml=$(curl -s "$listing_url")
    if [[ -z "$xml" ]]; then
        echo "Failed to fetch bucket listing for $dir_path"
        return
    fi
    files=$(echo "$xml" | grep -oP '<Key>\K[^<]+' | grep -v "/$")
    if [[ -z "$files" ]]; then
        echo "No files found in $dir_path"
        return
    fi
    for file in $files; do
        basename=$(basename "$file")
        url="${base_url}/${file}"
        echo "Attempting to download: $url"
        curl -f -s -o "${local_dir}/${basename}" "$url" || echo "Failed to download $url"
    done
}

function download_forcing_metadata() {
    local date=$1
    local cycle=$2
    local dir_path="${version}/ngen.${date}/forcing_${range}/${cycle}/metadata/forcings_metadata"
    local local_dir="${output_dir}/${dir_path}"
    mkdir -p "$local_dir"
    listing_url="${base_url}/?prefix=${dir_path}/&delimiter=/"
    echo "Fetching listing: $listing_url"
    xml=$(curl -s "$listing_url")
    if [[ -z "$xml" ]]; then
        echo "Failed to fetch bucket listing for $dir_path"
        return
    fi
    files=$(echo "$xml" | grep -oP '<Key>\K[^<]+' | grep -v "/$")
    if [[ -z "$files" ]]; then
        echo "No files found in $dir_path"
        return
    fi
    for file in $files; do
        basename=$(basename "$file")
        url="${base_url}/${file}"
        echo "Attempting to download: $url"
        curl -f -s -o "${local_dir}/${basename}" "$url" || echo "Failed to download $url"
    done
}

# Validate type
valid_types=("metadata" "forcing" "merkdir" "output" "resources" "forcing_metadata" "all")
if [[ ! " ${valid_types[@]} " =~ " ${type} " ]]; then
    echo "Error: Invalid type '$type'. Valid types are: ${valid_types[*]}"
    exit 1
fi

# Ensure output directory exists
mkdir -p "$output_dir" || { echo "Error: Cannot create output directory $output_dir"; exit 1; }

if [[ "$type" == "all" ]]; then
    types=("metadata" "forcing" "merkdir" "output" "forcing_metadata")
else
    types=("$type")
fi

for t in "${types[@]}"; do
    if [[ "$t" == "resources" ]]; then
        for vpu in "${vpu_array[@]}"; do
            if [[ "$vpu" == "-" ]]; then continue; fi
            download_resources "$vpu"
        done
    elif [[ "$t" == "forcing_metadata" ]]; then
        for date in "${date_array[@]}"; do
            if [[ "$date" == "-" ]]; then continue; fi
            for cycle in "${cycle_array[@]}"; do
                if [[ "$cycle" == "-" ]]; then continue; fi
                download_forcing_metadata "$date" "$cycle"
            done
        done
    else
        for date in "${date_array[@]}"; do
            if [[ "$date" == "-" ]]; then continue; fi
            for cycle in "${cycle_array[@]}"; do
                if [[ "$cycle" == "-" ]]; then continue; fi
                for vpu in "${vpu_array[@]}"; do
                    if [[ "$vpu" == "-" ]]; then continue; fi
                    case "$t" in
                        metadata) download_metadata "$date" "$cycle" "$vpu" ;;
                        forcing) download_forcing "$date" "$cycle" "$vpu" ;;
                        merkdir) download_merkdir "$date" "$cycle" "$vpu" ;;
                        output) download_output "$date" "$cycle" "$vpu" ;;
                        *) echo "Invalid type: $t"; exit 1 ;;
                    esac
                done
            done
        done
    fi
done