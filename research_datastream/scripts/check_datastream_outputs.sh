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

# Parse args (same as your script) ...
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

declare -A FORECAST_HOURS
FORECAST_HOURS[short_range]=$(seq -w 0 23)
FORECAST_HOURS[medium_range]="00 06 12 18"
FORECAST_HOURS[analysis_assim_extend]="16"

if [ "$VPUS" = "all" ]; then
    VPU_LIST="01 02 03N 03S 03W 04 05 06 07 08 09 10U 10L 11 12 13 14 15 16 17 18"
else
    VPU_LIST=$(echo "$VPUS" | sed 's/,/ /g')
fi

if [ "$RUN_TYPES" = "all" ]; then
    TYPES=("short_range" "medium_range" "analysis_assim_extend")
else
    TYPES=($(echo "$RUN_TYPES" | sed 's/,/ /g'))
fi

if [ "$INIT_CYCLES" != "all" ]; then
    temp_hours=$(echo "$INIT_CYCLES" | sed 's/,/ /g')
    HOURS_LIST=""
    for h in $temp_hours; do
        padded_h=$(printf "%02d" "${h#0}")
        HOURS_LIST="$HOURS_LIST $padded_h"
    done
    HOURS_LIST="${HOURS_LIST# }"
fi

if [ "$ENSEMBLES" = "all" ]; then
    ENSEMBLE_LIST="1 2 3 4 5 6 7"
else
    ENSEMBLE_LIST=$(echo "$ENSEMBLES" | sed 's/,/ /g')
fi

# Counters
declare -A SUCCESS FAIL

# Loop dates
for (( epoch = start_epoch; epoch <= end_epoch; epoch += 86400 )); do
    current_date=$(date -d @"$epoch" +%Y%m%d)

    for type in "${TYPES[@]}"; do
        if [ "$INIT_CYCLES" = "all" ]; then
            type_hours=${FORECAST_HOURS[$type]}
        else
            if [ "$type" = "analysis_assim_extend" ]; then
                type_hours="16"
            else
                type_hours="$HOURS_LIST"
            fi
        fi

        for hour in $type_hours; do
            for vpu in $VPU_LIST; do
                if [ "$type" = "medium_range" ]; then
                    for ens in $ENSEMBLE_LIST; do
                        url="${BASE_URL}/ngen.${current_date}/${type}/${hour}/${ens}/VPU_${vpu}/ngen-run.tar.gz"
                        status=$(curl -I -s -o /dev/null -w "%{http_code}" "$url")
                        key="ensemble_${ens}"
                        if [ "$status" = "200" ]; then
                            ((SUCCESS[$key]++))
                            ((SUCCESS["vpu_${vpu}"]++))
                            ((SUCCESS["type_${type}"]++))
                        else
                            echo "$url missing (status: $status)"
                            ((FAIL[$key]++))
                            ((FAIL["vpu_${vpu}"]++))
                            ((FAIL["type_${type}"]++))
                        fi
                    done
                else
                    url="${BASE_URL}/ngen.${current_date}/${type}/${hour}/VPU_${vpu}/ngen-run.tar.gz"
                    status=$(curl -I -s -o /dev/null -w "%{http_code}" "$url")
                    key="vpu_${vpu}"
                    if [ "$status" = "200" ]; then
                        ((SUCCESS[$key]++))
                        ((SUCCESS["type_${type}"]++))
                    else
                        echo "$url missing (status: $status)"
                        ((FAIL[$key]++))
                        ((FAIL["type_${type}"]++))
                    fi
                fi
            done
        done
    done
done

echo
echo "===== SUMMARY ====="

# --- Run types ---
echo "--- Run Types ---"
for type in "${TYPES[@]}"; do
    key="type_${type}"
    s=${SUCCESS[$key]:-0}
    f=${FAIL[$key]:-0}
    echo "${type}: successes=$s, failures=$f"
done
echo

# --- VPUs ---
echo "--- VPUs ---"
# Sort alphanumeric (handles 03N, 10U, etc.)
for vpu in $(printf "%s\n" $VPU_LIST | sort -V); do
    key="vpu_${vpu}"
    s=${SUCCESS[$key]:-0}
    f=${FAIL[$key]:-0}
    echo "${vpu}: successes=$s, failures=$f"
done
echo

# --- Ensembles ---
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

