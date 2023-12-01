#!/bin/bash
# set -x

if [ $# -ne 1 ]; then
    echo "Usage: $0 <datastream-config.json>"
    exit 1
fi

CONFIG_FILE="$1"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "File not found: $CONFIG_FILE"
    exit 1
fi
config=$(cat "$CONFIG_FILE")

GEOPACKAGE=$(echo "$config" | jq -r '.hydrofabric.geopackage')
SUBSET_ID=$(echo "$config" | jq -r '.hydrofabric.subset_id')
DATA_PATH=$(echo "$config" | jq -r '.globals.data_directory')
RELATIVE_TO=$(echo "$config" | jq -r '.globals.relative_to')

if [ -n "$RELATIVE_TO" ] && [ -n "$DATA_PATH" ]; then
    echo "Prepending ${RELATIVE_TO} to ${DATA_PATH#/}"
    DATA_PATH="${RELATIVE_TO%/}/${DATA_PATH#/}"
    GEOPACKAGE="${RELATIVE_TO%/}/${GEOPACKAGE#/}"
    echo $DATA_PATH
fi

if [ -e "$DATA_PATH" ]; then
    echo "The path $DATA_PATH exists. Please delete it or set a different path."
    # exit 1
else
    NGEN_CONFIG_PATH="${DATA_PATH%/}/ngen-run/config"
    DATASTREAM_MISC_PATH="${DATA_PATH%/}/misc"
    DATASTREAM_CONF_PATH="${DATA_PATH%/}/data-stream-configs"
    mkdir -p $DATA_PATH
    mkdir -p $NGEN_CONFIG_PATH
    mkdir -p $DATASTREAM_MISC_PATH
    mkdir -p $DATASTREAM_CONF_PATH
fi



SCRIPT_DIR=$(dirname "$(realpath "$0")")

echo "The script is located in: $SCRIPT_DIR\n"

# Subset
## hfsubset
# docker build /ngen-datastream/docker/hfsubset -t hfsubsetter –no-cache
# docker run -it --rm -v /path/to/your-directory:/mounted_dir hfsubsetter ./hfsubset -o ./mounted_dir/catchment-101subset.gpkg -r "v20" -t comid "101"
## subsetting
if [ -n "$SUBSET_ID" ]; then
    DOCKER_TAG="subsetter"
    SUBSET_DOCKER="$(dirname "$SCRIPT_DIR")/docker/subsetting"

    # Check if the Docker container exists
    if docker inspect "$DOCKER_TAG" &>/dev/null; then
        echo "The Docker container '$DOCKER_TAG' exists. Not building"
    else
        echo "Building subsetting container..."
        docker build $SUBSET_DOCKER -t subsetter --no-cache
    fi

    GEOPACKAGE_DIR=$(dirname ${GEOPACKAGE})
    GEOPACKAGE_NAME=$(basename "$GEOPACKAGE")

    docker run -it --rm -v $GEOPACKAGE_DIR:/mounted_dir -w /mounted_dir subsetter python /ngen-datastream/subsetting/src/subsetting/subset.py /mounted_dir/$GEOPACKAGE_NAME $SUBSET_ID

    GEOPACKAGE_SUBSETTED=$SUBSET_ID"_upstream_subset.gpkg"
    GEOPACKAGE="${GEOPACKAGE_DIR%/}/${GEOPACKAGE_SUBSETTED#/}"

    mv $GEOPACKAGE $NGEN_CONFIG_PATH

    files=("catchments.geojson" "crosswalk.json" "flowpath_edge_list.json" "flowpaths.geojson" "nexus.geojson")
    for file in "${files[@]}"; do
        mv "${GEOPACKAGE_DIR%/}/${file#/}" $DATASTREAM_MISC_PATH
    done

fi
# forcingprocessor
# docker build /ngen-datastream/docker/forcingprocessor -t forcingprocessor --no-cache
# docker run -it --rm -v /ngen-datastream:/mounted_dir forcingprocessor python /ngen-datastream/forcingprocessor/src/forcingprocessor/forcingprocessor.py /mounted_dir/forcingprocessor/configs/conf_docker.json

# tarballer

# validation
# docker build /ngen-datastream/docker/validator -t validator --no-cache
# docker run -it --rm -v /ngen-datastream:/mounted_dir validator python /ngen-cal/python/run_validator.py --data_dir /mounted_dir/data/standard_run

# hashing

