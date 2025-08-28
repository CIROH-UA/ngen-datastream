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

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --start) START_DATE="$2"; shift 2 ;;
        --end) END_DATE="$2"; shift 2 ;;
        --vpus) VPUS="$2"; shift 2 ;;
        --run_types) RUN_TYPES="$2"; shift 2 ;;
        --init_cycles) INIT_CYCLES="$2"; shift 2 ;;
        --ensembles) ENSEMBLES="$2"; shift 2 ;;
        *) usage ;;
    esac
done

# Check required inputs
if [ -z "$START_DATE" ] || [ -z "$END_DATE" ]; then
    usage
fi

# Defaults
VPUS=${VPUS:-16}
RUN_TYPES=${RUN_TYPES:-all}
INIT_CYCLES=${INIT_CYCLES:-all}
ENSEMBLES=${ENSEMBLES:-all}

# Epoch conversion
start_epoch=$(date -d "$START_DATE" +%s)
end_epoch=$(date -d "$END_DATE" +%s)

# Base URL
BASE_URL="https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2"

# Hours by type
declare -A FORECAST_HOURS
FORECAST_HOURS[short_range]=$(seq -w 0 23)
FORECAST_HOURS[medium_range]="00 06 12 18"
FORECAST_HOURS[analysis_assim_extend]="16"

# VPUs
if [ "$VPUS" = "all" ]; then
    VPU_LIST="01 02 03N 03S 03W 04 05 06 07 08 09 10U 10L 11 12 13 14 15 16 17 18"
else
    VPU_LIST=$(echo "$VPUS" | sed 's/,/ /g')
fi

# Types
if [ "$RUN_TYPES" = "all" ]; then
    TYPES=("short_range" "medium_range" "analysis_assim_extend")
else
    TYPES=($(echo "$RUN_TYPES" | sed 's/,/ /g'))
fi

# Hours
if [ "$INIT_CYCLES" != "all" ]; then
    HOURS_LIST=$(echo "$INIT_CYCLES" | sed 's/,/ /g' | xargs -n1 printf "%02d\n")
fi

# Ensembles
if [ "$ENSEMBLES" = "all" ]; then
    ENSEMBLE_LIST="1 2 3 4 5 6 7"
else
    ENSEMBLE_LIST=$(echo "$ENSEMBLES" | sed 's/,/ /g')
fi

# Loop over days
for (( epoch=start_epoch; epoch<=end_epoch; epoch+=86400 )); do
    current_date=$(date -d @"$epoch" +%Y%m%d)

    for type in "${TYPES[@]}"; do
        if [ "$INIT_CYCLES" = "all" ]; then
            type_hours=${FORECAST_HOURS[$type]}
        else
            type_hours=$HOURS_LIST
            [ "$type" = "analysis_assim_extend" ] && type_hours="16"
        fi

        for hour in $type_hours; do
            for vpu in $VPU_LIST; do
                if [ "$type" = "medium_range" ]; then
                    for ens in $ENSEMBLE_LIST; do
                        run_url="${BASE_URL}/ngen.${current_date}/${type}/${hour}/${ens}/VPU_${vpu}/ngen-run.tar.gz"
                        exec_url="${BASE_URL}/ngen.${current_date}/${type}/${hour}/${ens}/VPU_${vpu}/datastream-metadata/execution.json"
                        echo "Checking "$exec_url
                        status=$(curl -I -s -o /dev/null -w "%{http_code}" "$run_url")
                        if [ "$status" = "200" ]; then
                            # Pull execution.json and check retry_attempt
                            retry=$(curl -s "$exec_url" | jq -r '.retry_attempt')
			    echo "Retry count:"$retry
                            if [ "$retry" != "null" ] && [ "$retry" -gt 0 ]; then
                                echo "Retry detected ($retry): $exec_url"
                            fi
			else
				echo "Failed! "$exec_url
                        fi
                    done
                else
                    run_url="${BASE_URL}/ngen.${current_date}/${type}/${hour}/VPU_${vpu}/ngen-run.tar.gz"
                    exec_url="${BASE_URL}/ngen.${current_date}/${type}/${hour}/VPU_${vpu}/datastream-metadata/execution.json"

                    status=$(curl -I -s -o /dev/null -w "%{http_code}" "$run_url")
                    if [ "$status" = "200" ]; then
                        retry=$(curl -s "$exec_url" | jq -r '.retry_attempt')
			echo "Retry count:"$retry
                        if [ "$retry" != "null" ] && [ "$retry" -gt 0 ]; then
                            echo "Retry detected ($retry): $exec_url"
                        fi
                    fi
                fi
            done
        done
    done
done

