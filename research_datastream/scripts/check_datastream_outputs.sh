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

start_epoch=$(date -d "$START_DATE" +%s)
end_epoch=$(date -d "$END_DATE" +%s)

BASE_URL="https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2"

# --- Define valid init cycles for each type ---
declare -A INIT_CYCLES_ALLOWED
INIT_CYCLES_ALLOWED[short_range]="00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23"
INIT_CYCLES_ALLOWED[medium_range]="00 06 12 18"
INIT_CYCLES_ALLOWED[analysis_assim_extend]="16"

# VPU list
if [ "$VPUS" = "all" ]; then
    VPU_LIST="01 02 03N 03S 03W 04 05 06 07 08 09 10U 10L 11 12 13 14 15 16 17 18"
else
    VPU_LIST=$(echo "$VPUS" | sed 's/,/ /g')
fi

# Run types
if [ "$RUN_TYPES" = "all" ]; then
    TYPES=("short_range" "medium_range" "analysis_assim_extend")
else
    TYPES=($(echo "$RUN_TYPES" | sed 's/,/ /g'))
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
    ENSEMBLE_LIST="1 2 3 4 5 6 7"
else
    ENSEMBLE_LIST=$(echo "$ENSEMBLES" | sed 's/,/ /g')
fi

# Counters
declare -A SUCCESS FAIL
declare -A SUCCESS_INIT FAIL_INIT
declare -A SUCCESS_VPU_TYPE FAIL_VPU_TYPE   # NEW: per-VPU per-type

# Loop dates
for (( epoch = start_epoch; epoch <= end_epoch; epoch += 86400 )); do
    current_date=$(date -d @"$epoch" +%Y%m%d)

    for type in "${TYPES[@]}"; do
        allowed_hours=${INIT_CYCLES_ALLOWED[$type]}

        # Determine hours to check
        if [ "$INIT_CYCLES" = "all" ]; then
            type_hours="$allowed_hours"
        else
            type_hours=""
            for h in $CUSTOM_HOURS; do
                if [[ " $allowed_hours " =~ " $h " ]]; then
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
                            ((SUCCESS["vpu_${vpu}"]++))
                            ((SUCCESS["type_${type}"]++))
                            ((SUCCESS_VPU_TYPE["${vpu}_${type}"]++))
                            ((SUCCESS_INIT["${type}_${hour}"]++))
                        else
                            echo "$url missing (status: $status)"
                            ((FAIL["vpu_${vpu}"]++))
                            ((FAIL["type_${type}"]++))
                            ((FAIL_VPU_TYPE["${vpu}_${type}"]++))
                            ((FAIL_INIT["${type}_${hour}"]++))
                        fi
                    done
                else
                    url="${BASE_URL}/ngen.${current_date}/${type}/${hour}/VPU_${vpu}/ngen-run.tar.gz"
                    status=$(curl -I -s -o /dev/null -w "%{http_code}" "$url")
                    if [ "$status" = "200" ]; then
                        ((SUCCESS["vpu_${vpu}"]++))
                        ((SUCCESS["type_${type}"]++))
                        ((SUCCESS_VPU_TYPE["${vpu}_${type}"]++))
                        ((SUCCESS_INIT["${type}_${hour}"]++))
                    else
                        echo "$url missing (status: $status)"
                        ((FAIL["vpu_${vpu}"]++))
                        ((FAIL["type_${type}"]++))
                        ((FAIL_VPU_TYPE["${vpu}_${type}"]++))
                        ((FAIL_INIT["${type}_${hour}"]++))
                    fi
                fi
            done
        done
    done
done

# --- Summary function ---
print_summary() {
    echo
    echo "===== OVERALL SUMMARY ====="
    echo "--- Run Types ---"
    for type in "${TYPES[@]}"; do
        key="type_${type}"
        s=${SUCCESS[$key]:-0}
        f=${FAIL[$key]:-0}
        echo "${type}: successes=$s, failures=$f"
    done
    echo

    echo "--- VPUs ---"
    for vpu in $(printf "%s\n" $VPU_LIST | sort -V); do
        total_s=${SUCCESS["vpu_${vpu}"]:-0}
        total_f=${FAIL["vpu_${vpu}"]:-0}

        s_short=${SUCCESS_VPU_TYPE["${vpu}_short_range"]:-0}
        s_medium=${SUCCESS_VPU_TYPE["${vpu}_medium_range"]:-0}
        s_assim=${SUCCESS_VPU_TYPE["${vpu}_analysis_assim_extend"]:-0}

        f_short=${FAIL_VPU_TYPE["${vpu}_short_range"]:-0}
        f_medium=${FAIL_VPU_TYPE["${vpu}_medium_range"]:-0}
        f_assim=${FAIL_VPU_TYPE["${vpu}_analysis_assim_extend"]:-0}

        echo "${vpu}: successes=${total_s}(${s_short},${s_medium},${s_assim}), failures=${total_f}(${f_short},${f_medium},${f_assim})"
    done
    echo

    if [[ " ${TYPES[*]} " =~ " medium_range " ]]; then
        echo "--- Ensembles ---"
        for ens in $(echo $ENSEMBLE_LIST | tr ' ' '\n' | sort -n); do
            key="ensemble_${ens}"
            s=${SUCCESS[$key]:-0}
            f=${FAIL[$key]:-0}
            echo "${ens}: successes=$s, failures=$f"
        done
        echo
    fi
}

# --- Print single summary only ---
print_summary
