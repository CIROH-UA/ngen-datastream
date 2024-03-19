#!/bin/bash
set -e

SCRIPT_DIR=$(dirname "$(realpath "$0")")
PACAKGE_DIR=$(dirname $SCRIPT_DIR)
START_TIME=$(env TZ=US/Eastern date +'%Y%m%d%H%M%S')

get_file() {
    local FILE="$1"
    local OUTFILE="$2"

    if [[ "$FILE" == *"https://"* ]]; then
        curl -# -L -o "$OUTFILE" "$FILE"
    elif [[ "$FILE" == *"s3://"* ]]; then
        aws s3 sync "$FILE" "$OUTFILE"
    else
        if [ -e "$FILE" ]; then
            cp -r "$FILE" "$OUTFILE"
        else
            echo "$FILE doesn't exist!"
            exit 1
        fi
    fi
}

log_time() {
    local LABEL="$1"
    local LOG="$2"
    echo "$LABEL: $(env TZ=US/Eastern date +'%Y%m%d%H%M%S')" >> $LOG
}

usage() {
    echo ""
    echo "Usage: $0 [options]"
    echo "Either provide a datastream configuration file"
    echo "  -c, --CONF_FILE          <Path to datastream configuration file> "  
    echo "or run with cli args"
    echo "  -s, --START_DATE          <YYYYMMDDHHMM or \"DAILY\"> "
    echo "  -e, --END_DATE            <YYYYMMDDHHMM> "
    echo "  -d, --DATA_PATH           <Path to write to> "
    echo "  -r, --RESOURCE_PATH       <Path to resource directory> "
    echo "  -g, --GEOPACAKGE          <Path to geopackage file> "
    echo "  -G, --GEOPACAKGE_ATTR     <Path to geopackage attributes file> "
    echo "  -S, --S3_MOUNT            <Path to mount s3 bucket to>  "
    echo "  -o, --S3_PREFIX           <File prefix within s3 mount>"
    echo "  -i, --SUBSET_ID_TYPE      <Hydrofabric id type>  "   
    echo "  -I, --SUBSET_ID           <Hydrofabric id to subset>  "
    echo "  -v, --HYDROFABRIC_VERSION <Hydrofabric version> "
    echo "  -n, --NPROCS              <Process limit> "
    echo "  -D, --DOMAIN_NAME         <Name for spatial domain> "
    echo "  -h, --host_type           <Host type> "
    exit 1
}

START_DATE=""
END_DATE=""
DATA_PATH=""
RESOURCE_PATH=""
GEOPACKAGE=""
GEOPACKAGE_ATTR=""
S3_MOUNT=""
S3_PREFIX=""
SUBSET_ID_TYPE=""
SUBSET_ID=""
HYDROFABRIC_VERSION=""
CONF_FILE=""
NPROCS="$(( $(nproc) - 2 ))"
PKL_FILE=""
DOMAIN_NAME=""
HOST_TYPE=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        -s|--START_DATE) START_DATE="$2"; shift 2;;
        -e|--END_DATE) END_DATE="$2"; shift 2;;
        -d|--DATA_PATH) DATA_PATH="$2"; shift 2;;
        -r|--RESOURCE_PATH) RESOURCE_PATH="$2"; shift 2;;
        -g|--GEOPACKAGE) GEOPACKAGE="$2"; shift 2;;
        -G|--GEOPACKAGE_ATTR) GEOPACKAGE_ATTR="$2"; shift 2;;
        -S|--S3_MOUNT) S3_MOUNT="$2"; shift 2;;
        -o|--S3_PREFIX) S3_PREFIX="$2"; shift 2;;
        -i|--SUBSET_ID_TYPE) SUBSET_ID_TYPE="$2"; shift 2;;
        -I|--SUBSET_ID) SUBSET_ID="$2"; shift 2;;
        -v|--HYDROFABRIC_VERSION) HYDROFABRIC_VERSION="$2"; shift 2;;        
        -c|--CONF_FILE) CONF_FILE="$2"; shift 2;;
        -n|--NPROCS) NPROCS="$2"; shift 2;;
        -D|--DOMAIN_NAME) DOMAIN_NAME="$2"; shift 2;;
        -h|--HOST_TYPE) HOST_TYPE="$2"; shift 2;;
        *) usage;;
    esac
done

echo ""
echo "Running datastream with max ${NPROCS} processes"

if [ -n "$CONF_FILE" ]; then
    echo "Configuration option provided" $CONF_FILE
    if [ -e "$CONF_FILE" ]; then
        echo "Any variables defined in "$CONF_FILE" will override cli args"
        echo ""
        cat $CONF_FILE
        echo ""
        echo ""
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
    if [[ -z "$END_DATE" ]]; then
        if [[ -z "$DATA_PATH" ]]; then
            DATA_PATH="${PACAKGE_DIR%/}/data/$DATE"
        fi
        if [[ -n "${S3_MOUNT}" ]]; then     
            if [[ -z "${S3_PREFIX}" ]]; then
                S3_PREFIX="daily/$DATE" 
            fi
            S3_OUT="$S3_MOUNT/$S3_PREFIX"
            echo "S3_OUT: " $S3_OUT
            mkdir -p $S3_OUT 
        fi
    else
        if [[ -z "$DATA_PATH" ]]; then
            DATA_PATH="${PACAKGE_DIR%/}/data/${END_DATE::-4}"
        fi
        if [[ -n "${S3_MOUNT}" ]]; then
            if [[ -z "${S3_PREFIX}" ]]; then
                S3_PREFIX="daily/${END_DATE::-4}"
            fi 
            S3_OUT="$S3_MOUNT/$S3_PREFIX"
            echo "S3_OUT: " $S3_OUT
            mkdir -p $S3_OUT 
        fi
    fi
else
    if [[ -z "${DATA_PATH}" ]]; then
        DATA_PATH="${PACAKGE_DIR%/}/data/$START_DATE-$END_DATE"
    fi
    if [[ -n "${S3_MOUNT}" ]]; then
        S3_OUT="$S3_MOUNT/$START_DATE-$END_DATE"
        echo "S3_OUT: " $S3_OUT
        mkdir -p $S3_OUT
    fi
fi
DATA_PATH=$(readlink -f "$DATA_PATH")
RESOURCE_PATH=$(readlink -f "$RESOURCE_PATH")

if [ -e "$DATA_PATH" ]; then
    echo "The path $DATA_PATH exists. Please delete it or set a different path."
    exit 1
fi

mkdir -p $DATA_PATH
NGEN_RUN_PATH="${DATA_PATH%/}/ngen-run"

DATASTREAM_CONF_PATH="${DATA_PATH%/}/datastream-configs"
DATASTREAM_RESOURCES="${DATA_PATH%/}/datastream-resources"
DATASTREAM_PROFILING="${DATASTREAM_CONF_PATH%/}/profile.txt"
mkdir -p $DATASTREAM_CONF_PATH
touch $DATASTREAM_PROFILING
echo "START: $START_TIME" > $DATASTREAM_PROFILING

log_time "GET_RESOURCES_START" $DATASTREAM_PROFILING
NGEN_CONFIG_PATH="${NGEN_RUN_PATH%/}/config"
NGEN_OUTPUT_PATH="${NGEN_RUN_PATH%/}/outputs"
NGEN_RESTART_PATH="${NGEN_RUN_PATH%/}/restart"
NGEN_LAKEOUT_PATH="${NGEN_RUN_PATH%/}/lakeout"
mkdir -p $NGEN_CONFIG_PATH
mkdir -p $NGEN_OUTPUT_PATH
mkdir -p $NGEN_RESTART_PATH
mkdir -p $NGEN_LAKEOUT_PATH

GEOPACKGE_NGENRUN="datastream.gpkg"
GEOPACKAGE_NGENRUN_PATH="${NGEN_CONFIG_PATH%/}/$GEOPACKGE_NGENRUN"

get_file "$RESOURCE_PATH" $DATASTREAM_RESOURCES

if [ $START_DATE == "DAILY" ]; then
    :
else
    NWMURL_CONF_PATH=$(find "$DATASTREAM_RESOURCES" -type f -name "*nwmurl*")
    NNWMURL=$(find "$DATASTREAM_RESOURCES" -type f -name "*nwmurl*" | wc -l)
    if [ "$NNWMURL" -eq "0" ]; then
        echo "nwmurl_conf.json is missing from "$DATASTREAM_RESOURCES
        echo "exiting..."
        exit 1
    fi    
    if [ ${NNWMURL} -gt 1 ]; then
        echo "At most one nwmurl file is allowed in "$DATASTREAM_RESOURCES
    fi
    if [ -e "$NWMURL_CONF_PATH" ]; then 
        echo "Using $NWMURL_CONF_PATH"
    fi
fi

REALIZATION=$(find "$NGEN_CONFIG_PATH" -type f -name "realization")
if [ ! -f $REALIZATION ]; then
    echo "realization file is required"
    exit 1
fi

# Look for weights file
WEIGHTS_PATH=$(find "$DATASTREAM_RESOURCES" -type f -name "*weights*")
NWEIGHT=$(find "$DATASTREAM_RESOURCES" -type f -name "*weights" | wc -l)
if [ ${NWEIGHT} -gt 1 ]; then
    echo "At most one weight file is allowed in "$DATASTREAM_RESOURCES
fi

# Look for geopackage file
GEOPACKAGE_RESOURCES_PATH=$(find "$DATASTREAM_RESOURCES" -type f -name "*.gpkg")
NGEO=$(find "$DATASTREAM_RESOURCES" -type f -name "*.gpkg" | wc -l)
if [ ${NGEO} -gt 1 ]; then
    echo "At most one geopackage is allowed in "$DATASTREAM_RESOURCES
fi
GEOPACKAGE=$(basename $GEOPACKAGE_RESOURCES_PATH)

# Look for geopackage attributes file
# HACK: Should look for this in another way. Right now, this is the only parquet, but seems dangerous
if [ -z $GEOPACAKGE_ATTR ]; then
    GEOPACKAGE_ATTR=$(find "$DATASTREAM_RESOURCES" -type f -name "*.parquet")
    NATTR=$(find "$DATASTREAM_RESOURCES" -type f -name "*.parquet" | wc -l)
    if [ ${NATTR} != 1 ]; then
        echo "A single geopackage attributes file is requried"
    fi
    echo "Using "$GEOPACKAGE_ATTR "for geopackage attributes"
fi
ATTR_BASE=$(basename $GEOPACKAGE_ATTR)
if [ ! -f "$GEOPACKAGE_ATTR" ];then
    get_file $GEOPACKAGE_ATTR $NGEN_CONFIG_PATH/$ATTR_BASE
fi

# Look for pkl file
PKL_FILE=$(find "$DATASTREAM_RESOURCES" -type f -name "noah-owp-modular-init.namelist.input.pkl")

# Look for partitions file
PARTITION_RESOURCES_PATH=$(find "$DATASTREAM_RESOURCES" -type f -name "partitions")
if [ -e "$PARTITION_RESOURCES_PATH" ]; then
    PARTITION_NGENRUN_PATH=$NGEN_RUN_PATH/$(basename $PARTITION_RESOURCES_PATH)
    echo "Found $PARTITION_RESOURCES_PATH, copying to $PARTITION_NGENRUN_PATH"
    cp $PARTITION_RESOURCES_PATH $PARTITION_NGENRUN_PATH
fi

# Look for ngen configs folder
NGEN_CONFS="${DATASTREAM_RESOURCES%/}/ngen-configs/*"
cp $NGEN_CONFS $NGEN_CONFIG_PATH
if [ ${NGEO} == 1 ]; then
    GEO_BASE=$(basename $GEOPACKAGE_RESOURCES_PATH)
    mv $NGEN_CONFIG_PATH/$GEO_BASE $GEOPACKAGE_NGENRUN_PATH
fi
log_time "GET_RESOURCES_END" $DATASTREAM_PROFILING

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

if [[ -e $GEOPACKAGE_RESOURCES_PATH ]]; then
    :
else
    if [ "$SUBSET_ID" = "null" ] || [ -z "$SUBSET_ID" ]; then
        if [ ! -f "$GEOPACKAGE_RESOURCES_PATH" ]; then
            log_time "GEOPACKAGE_DL" $DATASTREAM_PROFILING
            GEO_BASE="$(basename $GEOPACKAGE)"
            GEOPACKAGE_RESOURCES_PATH="$DATASTREAM_RESOURCES/ngen-configs/$GEO_BASE"
            get_file "$GEOPACKAGE" "$GEOPACKAGE_RESOURCES_PATH"
            cp $GEOPACKAGE_RESOURCES_PATH $GEOPACKAGE_NGENRUN_PATH
            GEOPACKAGE="$GEO_BASE"
            log_time "GEOPACKAGE_DL" $DATASTREAM_PROFILING
        else
            echo "Geopackage does not exist and user has not specified subset! No way to determine spatial domain. Exiting." $GEOPACKAGE
            exit 1
        fi
    else
        log_time "SUBSET_START" $DATASTREAM_PROFILING
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
        log_time "SUBSET_END" $DATASTREAM_PROFILING
    fi   
fi

if [ -n "$DOMAIN_NAME" ]; then
    DOMAIN_NAME=${GEOPACKAGE%".gpkg"}
fi

log_time "WEIGHTS_START" $DATASTREAM_PROFILING
echo "Using geopackage $GEOPACKAGE, Named $GEOPACKGE_NGENRUN for ngen_run"

DOCKER_DIR="$(dirname "${SCRIPT_DIR%/}")/docker"
DOCKER_MOUNT="/mounted_dir"
DOCKER_RESOURCES="${DOCKER_MOUNT%/}/datastream-resources"
DOCKER_CONFIGS="${DOCKER_MOUNT%/}/datastream-configs"
DOCKER_FP_PATH="/ngen-datastream/forcingprocessor/src/forcingprocessor/"

DOCKER_TAG="forcingprocessor"
FP_DOCKER="${DOCKER_DIR%/}/forcingprocessor"

if [ -e "$WEIGHTS_PATH" ]; then
    echo "Using weights found in resources directory $WEIGHTS_PATH"
    if [[ $(basename $WEIGHTS_PATH) != "weights.json" ]]; then
        mv "$WEIGHTS_PATH" ""$DATASTREAM_RESOURCES"/weights.json"
    fi
else
    echo "Weights file not found. Creating from" $GEOPACKAGE

    GEO_PATH_DOCKER=""$DOCKER_RESOURCES"/ngen-configs/$GEOPACKAGE"
    WEIGHTS_DOCKER=""$DOCKER_RESOURCES"/weights.json"

    docker run -v "$DATA_PATH:"$DOCKER_MOUNT"" \
        -u $(id -u):$(id -g) \
        -w "$DOCKER_MOUNT" forcingprocessor \
        python "$DOCKER_FP_PATH"weights_parq2json.py \
        --gpkg $GEO_PATH_DOCKER --outname $WEIGHTS_DOCKER --nprocs $NPROCS

    WEIGHTS_FILE="${DATA%/}/${GEOPACKAGE#/}"
        
fi
log_time "WEIGHTS_END" $DATASTREAM_PROFILING


log_time "DATASTREAMCONFGEN_START" $DATASTREAM_PROFILING
DOCKER_TAG="datastream:latest"
echo "Generating ngen-datastream configs"
CONFIGURER="/ngen-datastream/python/src/datastream/configure-datastream.py"
docker run --rm -v "$DATA_PATH":"$DOCKER_MOUNT" $DOCKER_TAG \
    python $CONFIGURER \
    --docker_mount $DOCKER_MOUNT --start_date "$START_DATE" --end_date "$END_DATE" --data_path "$DATA_PATH" --resource_path "$RESOURCE_PATH" --gpkg "$GEOPACKAGE_RESOURCES_PATH" --gpkg_attr "$GEOPACKAGE_ATTR" --subset_id_type "$SUBSET_ID_TYPE" --subset_id "$SUBSET_ID" --hydrofabric_version "$HYDROFABRIC_VERSION" --nwmurl_file "$NWMURL_CONF_PATH" --nprocs "$NPROCS" --domain_name "$DOMAIN_NAME" --host_type "$HOST_TYPE"
log_time "DATASTREAMCONFGEN_END" $DATASTREAM_PROFILING

log_time "NGENCONFGEN_START" $DATASTREAM_PROFILING
if [ ! ${#PKL_FILE} -gt 1 ]; then
    echo "Generating noah-owp pickle file"
    NOAHOWPPKL_GENERATOR="/ngen-datastream/python/src/datastream/noahowp_pkl.py"
    PKL_FILE=$NGEN_CONFIG_PATH"/noah-owp-modular-init.namelist.input.pkl"
    docker run --rm -v "$NGEN_RUN_PATH":"$DOCKER_MOUNT" $DOCKER_TAG \
        python $NOAHOWPPKL_GENERATOR \
        --hf_lnk_file "$DOCKER_MOUNT/config/$ATTR_BASE" --outdir $DOCKER_MOUNT"/config"      
else
    cp $PKL_FILE "$NGEN_CONFIG_PATH" 
fi
PKL_BASE=$(basename $PKL_FILE)
PKL_FILE="$NGEN_CONFIG_PATH"/$PKL_BASE

echo "Generating NGEN configs"
NGEN_CONFGEN="/ngen-datastream/python/src/datastream/ngen_configs_gen.py"
docker run --rm -v "$NGEN_RUN_PATH":"$DOCKER_MOUNT" $DOCKER_TAG \
    python $NGEN_CONFGEN \
    --hf_file "$DOCKER_MOUNT/config/datastream.gpkg" --hf_lnk_file $DOCKER_MOUNT/config/$ATTR_BASE --outdir "$DOCKER_MOUNT/config" --pkl_file "$DOCKER_MOUNT/config"/$PKL_BASE --realization "$DOCKER_MOUNT/config/realization.json"
log_time "NGENCONFGEN_END" $DATASTREAM_PROFILING    


log_time "FORCINGPROCESSOR_START" $DATASTREAM_PROFILING
echo "Creating nwm filenames file"
DOCKER_TAG="forcingprocessor:latest"
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
log_time "FORCINGPROCESSOR_END" $DATASTREAM_PROFILING
    

log_time "VALIDATION_START" $DATASTREAM_PROFILING
VALIDATOR="/ngen-datastream/python/src/datastream/run_validator.py"
DOCKER_TAG="datastream:latest"
echo "Validating " $NGEN_RUN_PATH
docker run --rm -v "$NGEN_RUN_PATH":"$DOCKER_MOUNT" \
    $DOCKER_TAG python $VALIDATOR \
    --data_dir $DOCKER_MOUNT
log_time "VALIDATION_END" $DATASTREAM_PROFILING


log_time "NGEN_START" $DATASTREAM_PROFILING
echo "Running NextGen in AUTO MODE from CIROH-UA/NGIAB-CloudInfra"
docker run --rm -v "$NGEN_RUN_PATH":"$DOCKER_MOUNT" awiciroh/ciroh-ngen-image:latest "$DOCKER_MOUNT" auto $NPROCS
log_time "NGEN_END" $DATASTREAM_PROFILING


echo "$NGEN_RUN_PATH"/*.csv | xargs mv -t $NGEN_OUTPUT_PATH --


log_time "MERKLE_START" $DATASTREAM_PROFILING
docker run --rm -v "$DATA_PATH":"$DOCKER_MOUNT" zwills/merkdir /merkdir/merkdir gen -o $DOCKER_MOUNT/merkdir.file $DOCKER_MOUNT
log_time "MERKLE_END" $DATASTREAM_PROFILING


log_time "TAR_START" $DATASTREAM_PROFILING
TAR_NAME="ngen-run.tar.gz"
TAR_PATH="${DATA_PATH%/}/$TAR_NAME"
tar -cf - $NGEN_RUN_PATH | pigz > $TAR_PATH
log_time "TAR_END" $DATASTREAM_PROFILING

echo "ngen-datastream run complete!"

if [ -e "$S3_OUT" ]; then
    log_time "S3_MOVE_START" $DATASTREAM_PROFILING
    cp $TAR_PATH $S3_OUT
    cp $DATA_PATH/merkdir.file $S3_OUT
    cp -r $DATASTREAM_CONF_PATH $S3_OUT
    echo "Data exists here: $S3_OUT"
    log_time "S3_MOVE_END" $DATASTREAM_PROFILING
fi
echo "Data exists here: $DATA_PATH"
    