#!/bin/bash
set -e
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

START_DATE=$(echo "$config" | jq -r '.globals.start_date')
END_DATE=$(echo "$config" | jq -r '.globals.end_date')
DATA_PATH=$(echo "$config" | jq -r '.globals.data_dir')
RESOURCE_PATH=$(echo "$config" | jq -r '.globals.resource_dir')
RELATIVE_TO=$(echo "$config" | jq -r '.globals.relative_to')
GEOPACKAGE=$(echo "$config" | jq -r '.hydrofabric.geopackage')
SUBSET_ID=$(echo "$config" | jq -r '.hydrofabric.subset_id')

if [ -n "$RELATIVE_TO" ] && [ -n "$DATA_PATH" ]; then
    echo "Prepending ${RELATIVE_TO} to ${DATA_PATH#/}"
    DATA_PATH="${RELATIVE_TO%/}/${DATA_PATH%/}"
    RESOURCE_PATH="${RELATIVE_TO%/}/${RESOURCE_PATH%/}"
    GEOPACKAGE_FILE=$GEOPACKAGE
    GEOPACKAGE="${RESOURCE_PATH%/}/${GEOPACKAGE%/}"
    # echo $GEOPACKAGE
fi

if [ -e "$DATA_PATH" ]; then
    echo "The path $DATA_PATH exists. Please delete it or set a different path."
    # exit 1
fi

NGEN_CONFIG_PATH="${DATA_PATH%/}/ngen-run/config"
DATASTREAM_CONF_PATH="${DATA_PATH%/}/datastream-configs"
DATASTREAM_RESOURCES="${DATA_PATH%/}/datastream-resources"
mkdir -p $DATA_PATH
mkdir -p $NGEN_CONFIG_PATH
mkdir -p $DATASTREAM_CONF_PATH
cp -r $RESOURCE_PATH $DATASTREAM_RESOURCES
NGEN_CONFS="${DATASTREAM_RESOURCES%/}/ngen-configs/*"
cp $NGEN_CONFS $NGEN_CONFIG_PATH

SCRIPT_DIR=$(dirname "$(realpath "$0")")
DOCKER_MOUNT="/mounted_dir"
DOCKER_RESOURCES="${DOCKER_MOUNT%/}/datastream-resources"
DOCKER_CONFIGS="${DOCKER_MOUNT%/}/datastream-configs"
DOCKER_FP="/ngen-datastream/forcingprocessor/src/forcingprocessor/"

# Subset
## hfsubset
# docker build /ngen-datastream/docker/hfsubset -t hfsubsetter –no-cache
# docker run -it --rm -v /path/to/your-directory:/mounted_dir hfsubsetter ./hfsubset -o ./mounted_dir/catchment-101subset.gpkg -r "v20" -t comid "101"
## subsetting
if [ -n "$SUBSET_ID" ]; then
    DOCKER_TAG="subsetter"
    SUBSET_DOCKER="$(dirname "$SCRIPT_DIR")/docker/subsetting"

    if docker inspect "$DOCKER_TAG" &>/dev/null; then
        echo "The Docker container '$DOCKER_TAG' exists. Not building"
    else
        echo "Building subsetting container..."
        docker build $SUBSET_DOCKER -t subsetter --no-cache
    fi

    GEOPACKAGE_DIR=$(dirname ${GEOPACKAGE})
    GEOPACKAGE_NAME=$(basename "$GEOPACKAGE")

    docker run -it --rm -v "$GEOPACKAGE_DIR":"$DOCKER_MOUNT" -w "$DOCKER_MOUNT" subsetter python "/ngen-datastream/subsetting/src/subsetting/subset.py "$DOCKER_MOUNT"/$GEOPACKAGE_NAME" "$SUBSET_ID"

    GEOPACKAGE_FILE=$SUBSET_ID"_upstream_subset.gpkg"
    GEOPACKAGE="${GEOPACKAGE_DIR%/}/${GEOPACKAGE_FILE#/}"

    mv $GEOPACKAGE $NGEN_CONFIG_PATH

    files=("catchments.geojson" "crosswalk.json" "flowpath_edge_list.json" "flowpaths.geojson" "nexus.geojson")
    for file in "${files[@]}"; do
        mv "${GEOPACKAGE_DIR%/}/${file#/}" $DATASTREAM_RESOURCES
    done

else

    if [ -e "$GEOPACKAGE" ]; then
        echo "No subset_id provided, using provided geopackage" $GEOPACKAGE
        cp $GEOPACKAGE $NGEN_CONFIG_PATH
    else
        echo "Provided geopackage does not exist!" $GEOPACKAGE
        exit 1
    fi

fi

# forcingprocessor
DOCKER_TAG="forcingprocessor"
FP_DOCKER="$(dirname "$SCRIPT_DIR")/docker/forcingprocessor"

if docker inspect "$DOCKER_TAG" &>/dev/null; then
    echo "The Docker container '$DOCKER_TAG' exists. Not building"
else
    echo "Building subsetting container..."
    docker build $FP_DOCKER -t forcingprocessor --no-cache
fi

WEIGHTS_FILENAME=$(find "$DATASTREAM_RESOURCES" -type f -name "*weights*")
if [ -e "$WEIGHTS_FILENAME" ]; then
    echo "Using weights found in resources directory" "$WEIGHTS_FILENAME"
    mv "$WEIGHTS_FILENAME" ""$DATASTREAM_RESOURCES"/weights.json"
else
    echo "Weights file not found. Creating from" $GEOPACKAGE_FILE
    NWM_FILE=$(find "$DATASTREAM_RESOURCES" -type f -name "*nwm*")
    NWM_FILENAME=$(basename $NWM_FILE)

    GEO_PATH_DOCKER=""$DOCKER_RESOURCES"/$GEOPACKAGE_FILE"
    WEIGHTS_DOCKER=""$DOCKER_RESOURCES"/weights.json"
    NWM_DOCKER=""$DOCKER_RESOURCES"/$NWM_FILENAME"
    if [ -e "$NWM_FILE" ]; then
        echo "Found $NWM_FILE"
    else
        echo "Missing nwm example grid file!"
        exit 1
    fi
    docker run -it -v "$DATA_PATH:"$DOCKER_MOUNT"" forcingprocessor python "$DOCKER_FP"weight_generator.py $GEO_PATH_DOCKER $WEIGHTS_DOCKER $NWM_DOCKER
    WEIGHTS_FILE="${DATA%/}/${GEOPACKAGE_FILE#/}"
fi

CONF_GENERATOR="$(dirname "$SCRIPT_DIR")/python/configure-datastream.py"
python $CONF_GENERATOR $CONFIG_FILE

echo "Creating nwm files"
docker run -it --rm -v "$DATA_PATH:"$DOCKER_MOUNT"" -w "$DOCKER_RESOURCES" forcingprocessor python "$DOCKER_FP"nwm_filenames_generator.py "$DOCKER_MOUNT"/datastream-configs/conf_nwmurl.json

echo "Creating forcing files"
docker run -it --rm -v "$DATA_PATH:"$DOCKER_MOUNT"" forcingprocessor python "$DOCKER_FP"forcingprocessor.py "$DOCKER_CONFIGS"/conf_fp.json

# tarballer

# validation
# docker build /ngen-datastream/docker/validator -t validator --no-cache
# docker run -it --rm -v /ngen-datastream:"$DOCKER_MOUNT" validator python /ngen-cal/python/run_validator.py --data_dir "$DOCKER_MOUNT"/data/standard_run

# hashing

# ngen

# manage outputs
