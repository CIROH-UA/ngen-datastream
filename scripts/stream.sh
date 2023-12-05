#!/bin/bash
set -e
# set -x

build_docker_container() {
    local DOCKER_TAG="$1"
    local DOCKER_IMAGE="$2"

    if docker inspect "$DOCKER_TAG" &>/dev/null; then
        echo "The Docker container '$DOCKER_TAG' exists. Not building."
    else
        echo "Building $DOCKER_TAG container..."
        docker build "$DOCKER_IMAGE" -t "$DOCKER_TAG" --no-cache
    fi
}

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
fi

if [ -e "$DATA_PATH" ]; then
    echo "The path $DATA_PATH exists. Please delete it or set a different path."
    exit 1
fi

mkdir -p $DATA_PATH
NGEN_RUN_PATH="${DATA_PATH%/}/ngen-run"
DATASTREAM_CONF_PATH="${DATA_PATH%/}/datastream-configs"
DATASTREAM_RESOURCES="${DATA_PATH%/}/datastream-resources"
mkdir -p $DATASTREAM_CONF_PATH
cp -r $RESOURCE_PATH $DATASTREAM_RESOURCES

NGEN_CONFIG_PATH="${NGEN_RUN_PATH%/}/config"
NGEN_OUTPUT_PATH="${NGEN_RUN_PATH%/}/outputs"
mkdir -p $NGEN_CONFIG_PATH
mkdir -p $NGEN_OUTPUT_PATH

NGEN_CONFS="${DATASTREAM_RESOURCES%/}/ngen-configs/*"
cp $NGEN_CONFS $NGEN_CONFIG_PATH

SCRIPT_DIR=$(dirname "$(realpath "$0")")
DOCKER_DIR="$(dirname "${SCRIPT_DIR%/}")/docker"
DOCKER_MOUNT="/mounted_dir"
DOCKER_RESOURCES="${DOCKER_MOUNT%/}/datastream-resources"
DOCKER_CONFIGS="${DOCKER_MOUNT%/}/datastream-configs"
DOCKER_FP_PATH="/ngen-datastream/forcingprocessor/src/forcingprocessor/"

# Subset
## hfsubset
# docker build /ngen-datastream/docker/hfsubset -t hfsubsetter –no-cache
# docker run -it --rm -v /path/to/your-directory:/mounted_dir hfsubsetter ./hfsubset -o ./mounted_dir/catchment-101subset.gpkg -r "v20" -t comid "101"
## subsetting
if [ -n "$SUBSET_ID" ]; then
    DOCKER_TAG="subsetter"
    SUBSET_DOCKER="${DOCKER_DIR%/}/subsetting"
    build_docker_container "$DOCKER_TAG" "$SUBSET_DOCKER"

    GEOPACKAGE_DIR=$(dirname ${GEOPACKAGE})
    GEOPACKAGE_NAME=$(basename "$GEOPACKAGE")

    docker run -it --rm -v "$GEOPACKAGE_DIR":"$DOCKER_MOUNT" \
        -u $(id -u):$(id -g) -w "$DOCKER_RESOURCES" $DOCKER_TAG \
        python "/ngen-datastream/subsetting/src/subsetting/subset.py \
        "$DOCKER_MOUNT"/$GEOPACKAGE_NAME" "$SUBSET_ID"

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
FP_DOCKER="${DOCKER_DIR%/}/forcingprocessor"
build_docker_container "$DOCKER_TAG" "$FP_DOCKER"

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

    docker run -it -v "$DATA_PATH:"$DOCKER_MOUNT"" \
        -u $(id -u):$(id -g) \
        -w "$DOCKER_MOUNT" forcingprocessor \
        python "$DOCKER_FP_PATH"weight_generator.py \
        $GEO_PATH_DOCKER $WEIGHTS_DOCKER $NWM_DOCKER

    WEIGHTS_FILE="${DATA%/}/${GEOPACKAGE_FILE#/}"
fi

CONF_GENERATOR="$(dirname "$SCRIPT_DIR")/python/configure-datastream.py"
python $CONF_GENERATOR $CONFIG_FILE

echo "Creating nwm files"
docker run -it --rm -v "$DATA_PATH:"$DOCKER_MOUNT"" \
    -u $(id -u):$(id -g) \
    -w "$DOCKER_RESOURCES" $DOCKER_TAG \
    python "$DOCKER_FP_PATH"nwm_filenames_generator.py \
    "$DOCKER_MOUNT"/datastream-configs/conf_nwmurl.json

echo "Creating forcing files"
docker run -it --rm -v "$DATA_PATH:"$DOCKER_MOUNT"" \
    -u $(id -u):$(id -g) \
    -w "$DOCKER_RESOURCES" $DOCKER_TAG \
    python "$DOCKER_FP_PATH"forcingprocessor.py "$DOCKER_CONFIGS"/conf_fp.json

TAR_NAME="ngen-run.tar.gz"
TAR_PATH="${DATA_PATH%/}/$TAR_NAME"
tar -czf  $TAR_PATH -C $NGEN_RUN_PATH .

DOCKER_TAG="validator"
VAL_DOCKER="${DOCKER_DIR%/}/validator"
build_docker_container "$DOCKER_TAG" "$VAL_DOCKER"

TARBALL_DOCKER="${DOCKER_MOUNT%/}""/$TAR_NAME"
docker run -it --rm -v "$DATA_PATH":"$DOCKER_MOUNT" \
    validator python /ngen-cal/python/run_validator.py \
    --tarball $TARBALL_DOCKER

# hashing

# ngen

# manage outputs
