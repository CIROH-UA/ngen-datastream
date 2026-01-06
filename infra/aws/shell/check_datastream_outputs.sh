#!/bin/bash

# Function to display usage
usage() {
    echo "Usage: $0 --start YYYYMMDD --end YYYYMMDD [--vpus VPUS] [--run_types RUN_TYPES] [--init_cycles INIT_CYCLES] [--ensembles ENSEMBLES]"
    echo "VPUS: comma-separated list (e.g., '01,16,03N') or 'all'"
    echo "RUN_TYPES: comma-separated list (e.g., 'short_range,medium_range') or 'all' (default: all)"
    echo "INIT_CYCLES: comma-separated list (e.g., '00,06,12,18') or 'all' (default: all)"
    echo "ENSEMBLES: comma-separated list (e.g., '1,2,3,4,5,6,7') or 'all' (default: all, applies only to medium_range)"
    exit 1
}

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --start) START_DATE="$2"; shift 2;;
        --end) END_DATE="$2"; shift 2;;
        --vpus) VPUS="$2"; shift 2;;
        --run_types) RUN_TYPES="$2"; shift 2;;
        --init_cycles) INIT_CYCLES="$2"; shift 2;;
        --ensembles) ENSEMBLES="$2"; shift 2;;
        *) usage;;
    esac
done

if [ -z "$START_DATE" ] || [ -z "$END_DATE" ]; then usage; fi
if [ -z "$VPUS" ]; then VPUS="16"; fi
if [ -z "$RUN_TYPES" ]; then RUN_TYPES="all"; fi
if [ -z "$INIT_CYCLES" ]; then INIT_CYCLES="all"; fi
if [ -z "$ENSEMBLES" ]; then ENSEMBLES="all"; fi

# Cross-platform date conversion
date_to_epoch() {
    local dt="$1"
    if date --version >/dev/null 2>&1; then
        # GNU date (Linux)
        date -d "$dt" +%s
    else
        # BSD date (macOS)
        date -j -f "%Y%m%d" "$dt" +%s
    fi
}

epoch_to_date() {
    local ep="$1"
    if date --version >/dev/null 2>&1; then
        # GNU date (Linux)
        date -d "@$ep" +%Y%m%d
    else
        # BSD date (macOS)
        date -j -f "%s" "$ep" +%Y%m%d
    fi
}

start_epoch=$(date_to_epoch "$START_DATE")
end_epoch=$(date_to_epoch "$END_DATE")

BASE_URL="https://ciroh-community-ngen-datastream.s3.amazonaws.com/outputs/cfe_nom/v2.2_hydrofabric"

# Init cycles for each type
get_init_cycles() {
    local type="$1"
    case "$type" in
        short_range) echo "00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23";;
        medium_range) echo "00 06 12 18";;
        analysis_assim_extend) echo "16";;
    esac
}

# VPU list
if [ "$VPUS" = "all" ]; then
    VPU_LIST="01 02 03N 03S 03W 04 05 06 07 08 09 10U 10L 11 12 13 14 15 16 17 18"
else
    VPU_LIST=$(echo "$VPUS" | sed 's/,/ /g')
fi

# Run types
if [ "$RUN_TYPES" = "all" ]; then
    TYPES="short_range medium_range analysis_assim_extend"
else
    TYPES=$(echo "$RUN_TYPES" | sed 's/,/ /g')
fi

# Custom init cycles
CUSTOM_HOURS=""
if [ "$INIT_CYCLES" != "all" ]; then
    temp_hours=$(echo "$INIT_CYCLES" | sed 's/,/ /g')
    for h in $temp_hours; do
        padded_h=$(printf "%02d" "${h#0}")
        CUSTOM_HOURS="$CUSTOM_HOURS $padded_h"
    done
    CUSTOM_HOURS="${CUSTOM_HOURS# }"
fi

# Ensembles
if [ "$ENSEMBLES" = "all" ]; then
    ENSEMBLE_LIST="1"
else
    ENSEMBLE_LIST=$(echo "$ENSEMBLES" | sed 's/,/ /g')
fi

# Counters - use simple variables instead of associative arrays
success_total=0
fail_total=0
success_short_range=0
fail_short_range=0
success_medium_range=0
fail_medium_range=0
success_analysis_assim_extend=0
fail_analysis_assim_extend=0

# Track failures
FAILURES=""

# Loop dates
epoch=$start_epoch
while [ "$epoch" -le "$end_epoch" ]; do
    current_date=$(epoch_to_date "$epoch")

    for type in $TYPES; do
        allowed_hours=$(get_init_cycles "$type")

        # Determine hours to check
        if [ "$INIT_CYCLES" = "all" ]; then
            type_hours="$allowed_hours"
        else
            type_hours=""
            for h in $CUSTOM_HOURS; do
                if echo " $allowed_hours " | grep -q " $h "; then
                    type_hours="$type_hours $h"
                fi
            done
            type_hours="${type_hours# }"
        fi
        [ -z "$type_hours" ] && continue

        for hour in $type_hours; do
            for vpu in $VPU_LIST; do
                if [ "$type" = "medium_range" ]; then
                    for ens in $ENSEMBLE_LIST; do
                        url="${BASE_URL}/ngen.${current_date}/${type}/${hour}/${ens}/VPU_${vpu}/ngen-run.tar.gz"
                        status=$(curl -I -s -o /dev/null -w "%{http_code}" "$url")
                        if [ "$status" = "200" ]; then
                            success_total=$((success_total + 1))
                            success_medium_range=$((success_medium_range + 1))
                        else
                            echo "$url missing (status: $status)"
                            fail_total=$((fail_total + 1))
                            fail_medium_range=$((fail_medium_range + 1))
                            FAILURES="$FAILURES\n$url"
                        fi
                    done
                else
                    url="${BASE_URL}/ngen.${current_date}/${type}/${hour}/VPU_${vpu}/ngen-run.tar.gz"
                    status=$(curl -I -s -o /dev/null -w "%{http_code}" "$url")
                    if [ "$status" = "200" ]; then
                        success_total=$((success_total + 1))
                        case "$type" in
                            short_range) success_short_range=$((success_short_range + 1));;
                            analysis_assim_extend) success_analysis_assim_extend=$((success_analysis_assim_extend + 1));;
                        esac
                    else
                        echo "$url missing (status: $status)"
                        fail_total=$((fail_total + 1))
                        case "$type" in
                            short_range) fail_short_range=$((fail_short_range + 1));;
                            analysis_assim_extend) fail_analysis_assim_extend=$((fail_analysis_assim_extend + 1));;
                        esac
                        FAILURES="$FAILURES\n$url"
                    fi
                fi
            done
        done
    done

    # Increment by one day (86400 seconds)
    epoch=$((epoch + 86400))
done

# Summary
echo ""
echo "===== OVERALL SUMMARY ====="
echo "--- Run Types ---"
for type in $TYPES; do
    case "$type" in
        short_range) echo "short_range: successes=$success_short_range, failures=$fail_short_range";;
        medium_range) echo "medium_range: successes=$success_medium_range, failures=$fail_medium_range";;
        analysis_assim_extend) echo "analysis_assim_extend: successes=$success_analysis_assim_extend, failures=$fail_analysis_assim_extend";;
    esac
done
echo ""
echo "--- Total ---"
echo "Successes: $success_total"
echo "Failures: $fail_total"
echo ""

if [ "$fail_total" -gt 0 ]; then
    exit 1
else
    exit 0
fi
