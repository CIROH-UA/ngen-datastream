#!/bin/bash
set -e

SCRIPT_DIR=$(dirname "$(realpath "$0")")
PACAKGE_DIR=$(dirname $SCRIPT_DIR)

build_docker_container() {
    local DOCKER_TAG="$1"
    local DOCKER_IMAGE="$2"

    if docker inspect "$DOCKER_TAG" &>/dev/null; then
        echo "The Docker container "$DOCKER_TAG" exists. Not building."
    else
        echo "Building $DOCKER_TAG container..."
        docker build $DOCKER_IMAGE -t $DOCKER_TAG --no-cache
    fi
}

usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -s, --start-date <start_date>         "
    echo "  -e, --end-date <end_date>             "
    echo "  -d, --data-path <data_path>           "
    echo "  -r, --resource-path <resource_path>   "
    echo "  -t, --relative-to <relative_to>       "
    echo "  -i, --id-type <id_type>               "
    echo "  -I, --id <id>                         "
    echo "  -v, --version <version>               "
    echo "  -c, --conf-file <conf_file>           "
    exit 1
}

START_DATE=""
END_DATE=""
DATA_PATH=""
RESOURCE_PATH=""
RELATIVE_TO=""
S3_MOUNT=""
SUBSET_ID_TYPE=""
SUBSET_ID=""
HYDROFABRIC_VERSION=""
CONF_FILE=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        -s|--start-date) START_DATE="$2"; shift 2;;
        -e|--end-date) END_DATE="$2"; shift 2;;
        -d|--data-path) DATA_PATH="$2"; shift 2;;
        -r|--resource-path) RESOURCE_PATH="$2"; shift 2;;
        -t|--relative-to) RELATIVE_TO="$2"; shift 2;;
        -i|--id-type) SUBSET_ID_TYPE="$2"; shift 2;;
        -I|--id) SUBSET_ID="$2"; shift 2;;
        -v|--version) HYDROFABRIC_VERSION="$2"; shift 2;;
        -S|--s3-mount) S3_MOUNT="$2"; shift 2;;
        -c|--conf-file) CONF_FILE="$2"; shift 2;;
        *) usage;;
    esac
done

if [ -n "$CONF_FILE" ]; then
    echo "Configuration option provided" $CONF_FILE
    if [ -e "$CONF_FILE" ]; then
        echo "Any variables defined in "$CONF_FILE" will override cli args"
        echo "Using options:"
        cat $CONF_FILE
        source "$CONF_FILE"
    else
        echo $CONF_FILE" not found!!"
        exit 1
    fi
else
    echo "No configuration file detected, using cli args"
fi

if [ -n "$SUBSET_ID" ]; then    
    if [ $HYDROFABRIC_VERSION == "v20.1" ]; then
        :
    else
        echo "Subsetting and weight generation are not supported for hydrofabric versions less than v20.1, set to v20.1"
        exit
    fi
fi

DATE=$(env TZ=US/Eastern date +'%Y%m%d')
if [ $START_DATE == "DAILY" ]; then
    if [ -z $END_DATE ]; then
        DATA_PATH="${PACAKGE_DIR%/}/data/$DATE"
    else
        DATA_PATH="${PACAKGE_DIR%/}/data/$END_DATE"
    fi
    if [ -n "${S3_MOUNT}" ]; then
        S3_OUT="$S3_MOUNT/daily/$DATE"
        echo "S3_OUT: " $S3_OUT
        mkdir -p $S3_OUT        
    fi
else
    if [ -z "${DATA_PATH}" ]; then
        DATA_PATH="${PACAKGE_DIR%/}/data/$START_DATE-$END_DATE"
    fi
    if [ -n "${S3_MOUNT}" ]; then
        S3_OUT="$S3_MOUNT/$START_DATE-$END_DATE"
        echo "S3_OUT: " $S3_OUT
        mkdir -p $S3_OUT
    fi
fi

echo "DATA_PATH: " $DATA_PATH

if [ ${#RELATIVE_TO} -gt 0 ] ; then
    echo "Prepending ${RELATIVE_TO} to ${DATA_PATH#/}"
    DATA_PATH="${RELATIVE_TO%/}/${DATA_PATH%/}"
    if [ -n "$RESOURCE_PATH" ]; then
        echo "Prepending ${RELATIVE_TO} to ${RESOURCE_PATH#/}"
        RESOURCE_PATH="${RELATIVE_TO%/}/${RESOURCE_PATH%/}"
    fi
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

NGEN_CONFIG_PATH="${NGEN_RUN_PATH%/}/config"
NGEN_OUTPUT_PATH="${NGEN_RUN_PATH%/}/outputs"
mkdir -p $NGEN_CONFIG_PATH
mkdir -p $NGEN_OUTPUT_PATH

GEOPACKGE_NGENRUN="datastream.gpkg"
GEOPACKAGE_NGENRUN_PATH="${NGEN_CONFIG_PATH%/}/$GEOPACKGE_NGENRUN"

if [ -z "$RESOURCE_PATH" ]; then    
    echo "No resource path provided. Generating datastream resources with defaults"
    RESOURCES_DEFAULT="s3://ngen-datastream/resources_default"
    aws s3 sync $RESOURCES_DEFAULT $DATASTREAM_RESOURCES
else    
    echo "Resource path option provided" $RESOURCE_PATH
    if [[ $RESOURCE_PATH == *"https://"* ]]; then
        echo "curl'ing $DATASTREAM_RESOURCES $RESOURCE_PATH"
        curl -# -L -o $DATASTREAM_RESOURCES $RESOURCE_PATH
    elif [ $RESOURCE_PATH == *"s3://"* ]; then
        aws s3 sync $RESOURCE_PATH $DATASTREAM_RESOURCES
    else
        if [ -e "$RESOURCE_PATH" ]; then
            echo "Copying into current data path "$DATA_PATH
            cp -r $RESOURCE_PATH $DATASTREAM_RESOURCES
        else
            echo $RESOURCE_PATH " provided doesn't exist!"
        fi
    fi
fi

if [[ $RESOURCE_PATH == *".tar."* ]]; then
    echo UNTESTED
    tar -xzvf $(basename $RESOURCE_PATH)
fi

WEIGHTS_PATH=$(find "$DATASTREAM_RESOURCES" -type f -name "*weights*")
NWEIGHT=$(find "$DATASTREAM_RESOURCES" -type f -name "*weights" | wc -l)
if [ ${NWEIGHT} -gt 1 ]; then
    echo "At most one weight file is allowed in "$DATASTREAM_RESOURCES
fi

NWMURL_CONF_PATH=$(find "$DATASTREAM_RESOURCES" -type f -name "nwmurl")
NNWMURL=$(find "$DATASTREAM_RESOURCES" -type f -name "*nwmurl" | wc -l)
if [ ${NNWMURL} -gt 1 ]; then
    echo "At most one nwmurl file is allowed in "$DATASTREAM_RESOURCES
fi
if [ -e "$NWMURL_CONF_PATH" ]; then 
    echo "Using $NWMURL_CONF_PATH"
fi

GEOPACKAGE_RESOURCES_PATH=$(find "$DATASTREAM_RESOURCES" -type f -name "*.gpkg")
NGEO=$(find "$DATASTREAM_RESOURCES" -type f -name "*.gpkg" | wc -l)
if [ ${NGEO} -gt 1 ]; then
    echo "At most one geopackage is allowed in "$DATASTREAM_RESOURCES
fi

PARTITION_RESOURCES_PATH=$(find "$DATASTREAM_RESOURCES" -type f -name "partitions")
if [ -e "$PARTITION_RESOURCES_PATH" ]; then
    PARTITION_NGENRUN_PATH=$NGEN_RUN_PATH/$(basename $PARTITION_RESOURCES_PATH)
    echo "Found $PARTITION_RESOURCES_PATH, copying to $PARTITION_NGENRUN_PATH"
    cp $PARTITION_RESOURCES_PATH $PARTITION_NGENRUN_PATH
fi

NGEN_CONFS="${DATASTREAM_RESOURCES%/}/ngen-configs/*"
cp $NGEN_CONFS $NGEN_CONFIG_PATH

if [ -z "$SUBSET_ID" ]; then
    :
else
    if [ -e $GEOPACKAGE_RESOURCES_PATH ]; then
        echo "Overriding "$GEOPACKAGE_RESOURCES_PATH" with $SUBSET_ID"
        GEOPACKAGE_RESOURCES_PATH="NULL"
    fi
    if [ -e $WEIGHTS_PATH ]; then
        echo "Overriding "$WEIGHTS_PATH" with $SUBSET_ID"
        WEIGHTS_PATH="NULL"
    fi    
fi

if [ -e $GEOPACKAGE_RESOURCES_PATH ]; then
    GEOPACKAGE=$(basename $GEOPACKAGE_RESOURCES_PATH)
    cp $GEOPACKAGE_RESOURCES_PATH $GEOPACKAGE_NGENRUN_PATH
else
    if [ "$SUBSET_ID" = "null" ] || [ -z "$SUBSET_ID" ]; then
        echo "Geopackage does not exist and user has not specified subset! No way to determine spatial domain. Exiting." $GEOPACKAGE
        exit 1
    else

        GEOPACKAGE="$SUBSET_ID.gpkg"
        GEOPACKAGE_RESOURCES_PATH="${DATASTREAM_RESOURCES%/}/$GEOPACKAGE"

        if command -v "hfsubset" &>/dev/null; then
            echo "hfsubset is installed and available in the system's PATH. Subsetting, now!"
        else
            curl -L -o "$DATASTREAM_RESOURCES/hfsubset-linux_amd64.tar.gz" https://github.com/LynkerIntel/hfsubset/releases/download/hfsubset-release-12/hfsubset-linux_amd64.tar.gz
            tar -xzvf "$DATASTREAM_RESOURCES/hfsubset-linux_amd64.tar.gz"
        fi

        hfsubset -o $GEOPACKAGE_RESOURCES_PATH -r $HYDROFABRIC_VERSION -t $SUBSET_ID_TYPE $SUBSET_ID

        cp $GEOPACKAGE_RESOURCES_PATH $GEOPACKAGE_NGENRUN_PATH        

    fi        
fi

echo "Using geopackage $GEOPACKAGE, Named $GEOPACKGE_NGENRUN for ngen_run"

DOCKER_DIR="$(dirname "${SCRIPT_DIR%/}")/docker"
DOCKER_MOUNT="/mounted_dir"
DOCKER_RESOURCES="${DOCKER_MOUNT%/}/datastream-resources"
DOCKER_CONFIGS="${DOCKER_MOUNT%/}/datastream-configs"
DOCKER_FP_PATH="/ngen-datastream/forcingprocessor/src/forcingprocessor/"

DOCKER_TAG="forcingprocessor"
FP_DOCKER="${DOCKER_DIR%/}/forcingprocessor"
build_docker_container "$DOCKER_TAG" "$FP_DOCKER"

if [ -e "$WEIGHTS_PATH" ]; then
    echo "Using weights found in resources directory $WEIGHTS_PATH"
    if [[ $(basename $WEIGHTS_PATH) != "weights.json" ]]; then
        mv "$WEIGHTS_PATH" ""$DATASTREAM_RESOURCES"/weights.json"
    fi
else
    echo "Weights file not found. Creating from" $GEOPACKAGE

    GEO_PATH_DOCKER=""$DOCKER_RESOURCES"/$GEOPACKAGE"
    WEIGHTS_DOCKER=""$DOCKER_RESOURCES"/weights.json"

    docker run -v "$DATA_PATH:"$DOCKER_MOUNT"" \
        -u $(id -u):$(id -g) \
        -w "$DOCKER_MOUNT" forcingprocessor \
        python "$DOCKER_FP_PATH"weights_parq2json.py \
        --gpkg $GEO_PATH_DOCKER --outname $WEIGHTS_DOCKER

    WEIGHTS_FILE="${DATA%/}/${GEOPACKAGE#/}"
        
fi

CONF_GENERATOR="$PACAKGE_DIR/python/configure-datastream.py"
python3 $CONF_GENERATOR \
    --start-date "$START_DATE" \
    --end-date "$END_DATE" \
    --data-dir "$DATA_PATH" \
    --relative-to "$RELATIVE_TO" \
    --resource-dir "$RESOURCE_PATH" \
    --subset-id-type "$SUBSET_ID_TYPE" \
    --subset-id "$SUBSET_ID" \
    --hydrofabric-version "$HYDROFABRIC_VERSION" \
    --nwmurl_file "$NWMURL_CONF_PATH"

echo "Creating nwm filenames file"
docker run --rm -v "$DATA_PATH:"$DOCKER_MOUNT"" \
    -u $(id -u):$(id -g) \
    -w "$DOCKER_RESOURCES" $DOCKER_TAG \
    python "$DOCKER_FP_PATH"nwm_filenames_generator.py \
    "$DOCKER_MOUNT"/datastream-configs/conf_nwmurl.json

echo "Creating forcing files"
docker run --rm -v "$DATA_PATH:"$DOCKER_MOUNT"" \
    -u $(id -u):$(id -g) \
    -w "$DOCKER_RESOURCES" $DOCKER_TAG \
    python "$DOCKER_FP_PATH"forcingprocessor.py "$DOCKER_CONFIGS"/conf_fp.json

VALIDATOR="/ngen-datastream/python/run_validator.py"
DOCKER_TAG="validator"
VAL_DOCKER="${DOCKER_DIR%/}/validator"
build_docker_container "$DOCKER_TAG" "$VAL_DOCKER"
    
echo "Validating " $NGEN_RUN_PATH
docker run --rm -v "$NGEN_RUN_PATH":"$DOCKER_MOUNT" \
    validator python $VALIDATOR \
    --data_dir $DOCKER_MOUNT

echo "Running NextGen in AUTO MODE from CIROH-UA/NGIAB-CloudInfra"
docker run --rm -v "$NGEN_RUN_PATH":"$DOCKER_MOUNT" awiciroh/ciroh-ngen-image:latest-local "$DOCKER_MOUNT" auto

echo "$NGEN_RUN_PATH"/*.csv | xargs mv -t $NGEN_OUTPUT_PATH --
 
docker run --rm -v "$DATA_PATH":"$DOCKER_MOUNT" zwills/merkdir /merkdir/merkdir gen -o $DOCKER_MOUNT/merkdir.file $DOCKER_MOUNT

TAR_NAME="ngen-run.tar.gz"
TAR_PATH="${DATA_PATH%/}/$TAR_NAME"
tar -cf - $NGEN_RUN_PATH | pigz > $TAR_PATH

echo "ngen-datastream run complete!"

if [ -n "$S3_OUT" ]; then
    cp $TAR_PATH $S3_OUT
    cp $DATA_PATH/merkdir.file $S3_OUT
    cp -r $DATASTREAM_CONF_PATH $S3_OUT
    echo "Data exists here: $S3_OUT"
fi
echo "Data exists here: $DATA_PATH"
    