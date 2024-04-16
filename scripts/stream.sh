#!/bin/bash
set -e

SCRIPT_DIR=$(dirname "$(realpath "$0")")
PACAKGE_DIR=$(dirname $SCRIPT_DIR)
START_TIME=$(env TZ=US/Eastern date +'%Y%m%d%H%M%S')

get_file() {
    local FILE="$1"
    local OUTFILE="$2"

    echo "Retrieving "$FILE" and storing it here "$OUTFILE

    if [[ "$FILE" == *"https://"* ]]; then
        curl -# -L -o "$OUTFILE" "$FILE"
    elif [[ "$FILE" == *"s3://"* ]]; then
        aws s3 cp "$FILE" "$OUTFILE"
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
    echo "  -R, --REALIZATION         <Path to realization file> "
    echo "  -r, --RESOURCE_PATH       <Path to resource directory> "
    echo "  -f, --FORCINGS_PATH       <Path to forcings tarball> "
    echo "  -g, --GEOPACAKGE          <Path to geopackage file> "
    echo "  -G, --GEOPACKAGE_ATTR     <Path to geopackage attributes file> "
    echo "  -S, --S3_MOUNT            <Path to mount s3 bucket to>  "
    echo "  -o, --S3_PREFIX           <File prefix within s3 mount>"
    echo "  -i, --SUBSET_ID_TYPE      <Hydrofabric id type>  "   
    echo "  -I, --SUBSET_ID           <Hydrofabric id to subset>  "
    echo "  -v, --HYDROFABRIC_VERSION <Hydrofabric version> "
    echo "  -n, --NPROCS              <Process limit> "
    echo "  -D, --DOMAIN_NAME         <Name for spatial domain> "
    exit 1
}

# init variables
START_DATE=""
END_DATE=""
DATA_PATH=""
REALIZATION=""
RESOURCE_PATH=""
FORCINGS_TAR=""
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
if ! command -v ec2-metadata >/dev/null 2>&1; then
    HOST_TYPE="NON-AWS"
else
    HOST_TYPE=$(ec2-metadata --instance-type)
    HOST_TYPE=$(echo "$HOST_TYPE" | awk -F': ' '{print $2}')
fi
echo "HOST_TYPE" $HOST_TYPE
HOST_OS=$(cat /etc/os-release | grep "PRETTY_NAME")
HOST_OS=$(echo "$HOST_OS" | sed 's/.*"\(.*\)"/\1/')
echo "HOST_OS" $HOST_OS

# read cli args
while [ "$#" -gt 0 ]; do
    case "$1" in
        -s|--START_DATE) START_DATE="$2"; shift 2;;
        -e|--END_DATE) END_DATE="$2"; shift 2;;
        -d|--DATA_PATH) DATA_PATH="$2"; shift 2;;
        -R|--REALIZATION) REALIZATION="$2"; shift 2;;
        -r|--RESOURCE_PATH) RESOURCE_PATH="$2"; shift 2;;
        -f|--FORCINGS_TAR) FORCINGS_TAR="$2"; shift 2;;
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
        *) usage;;
    esac
done

echo "Running datastream with max ${NPROCS} processes"

if [ ! -z $CONF_FILE ]; then
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

# force hydrofabric version for now
if [ ! -z $SUBSET_ID ]; then    
    if [ $HYDROFABRIC_VERSION == "v20.1" ]; then
        :
    else
        echo "Subsetting and weight generation are not supported for hydrofabric versions less than v20.1, set to v20.1"
        exit
    fi
fi

# set paths for daily run
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

# create directories
DATA_PATH=$(readlink -f "$DATA_PATH")
if [ -e "$DATA_PATH" ]; then
    echo "The path $DATA_PATH exists. Please delete it or set a different path."
    exit 1
fi

mkdir -p $DATA_PATH
NGEN_RUN_PATH="${DATA_PATH%/}/ngen-run"

DATASTREAM_META_PATH="${DATA_PATH%/}/datastream-metadata"
DATASTREAM_RESOURCES="${DATA_PATH%/}/datastream-resources"
DATASTREAM_RESOURCES_NGENCONF_PATH="${DATASTREAM_RESOURCES%/}/ngen-configs/"
NGEN_BMI_CONFS="${DATASTREAM_RESOURCES_NGENCONF_PATH%/}/ngen-bmi-configs.tar.gz"
DATASTREAM_PROFILING="${DATASTREAM_META_PATH%/}/profile.txt"
mkdir -p $DATASTREAM_META_PATH
touch $DATASTREAM_PROFILING
echo "DATASTREAM_START: $START_TIME" > $DATASTREAM_PROFILING

NGEN_CONFIG_PATH="${NGEN_RUN_PATH%/}/config"
NGEN_FORCINGS_PATH="${NGEN_RUN_PATH%/}/forcings"
NGEN_OUTPUT_PATH="${NGEN_RUN_PATH%/}/outputs"
NGEN_RESTART_PATH="${NGEN_RUN_PATH%/}/restart"
NGEN_LAKEOUT_PATH="${NGEN_RUN_PATH%/}/lakeout"
mkdir -p $NGEN_CONFIG_PATH
mkdir -p $NGEN_OUTPUT_PATH
mkdir -p $NGEN_RESTART_PATH
mkdir -p $NGEN_LAKEOUT_PATH

DOCKER_DIR="$(dirname "${SCRIPT_DIR%/}")/docker"
DOCKER_MOUNT="/mounted_dir"
DOCKER_RESOURCES="${DOCKER_MOUNT%/}/datastream-resources"
DOCKER_META="${DOCKER_MOUNT%/}/datastream-metadata"
DOCKER_FP_PATH="/ngen-datastream/forcingprocessor/src/forcingprocessor/"

log_time "GET_RESOURCES_START" $DATASTREAM_PROFILING
if [ ! -z $RESOURCE_PATH ]; then
    echo "running in lite mode"
    RESOURCE_PATH=$(readlink -f "$RESOURCE_PATH")
    get_file "$RESOURCE_PATH" $DATASTREAM_RESOURCES
else
    echo "running in standard mode"
    mkdir -p $DATASTREAM_RESOURCES
    mkdir -p $DATASTREAM_RESOURCES_NGENCONF_PATH
fi

if [ -z $FORCINGS_TAR ]; then
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
fi

if [ ! -z $SUBSET_ID ]; then
    log_time "SUBSET_START" $DATASTREAM_PROFILING
    GEOPACKAGE="$SUBSET_ID.gpkg"
    GEOPACKAGE_RESOURCES_PATH="${DATASTREAM_RESOURCES%/}/$GEOPACKAGE"
    hfsubset -o $GEOPACKAGE_RESOURCES_PATH -r $HYDROFABRIC_VERSION -t $SUBSET_ID_TYPE $SUBSET_ID
    cp $GEOPACKAGE_RESOURCES_PATH $GEOPACKAGE_NGENRUN_PATH        
    log_time "SUBSET_END" $DATASTREAM_PROFILING
fi   

if [ ! -z $RESOURCE_PATH ]; then  

    # Look for realization
    REALIZATION_RESOURCES_PATH=$(find "$DATASTREAM_RESOURCES_NGENCONF_PATH" -type f -name "*realization*")
    if [ ! -f $REALIZATION_RESOURCES_PATH ]; then
        echo "realization file is required in RESOURCE_PATH/ngen-configs"
        exit 1
    else
        REAL_BASE=$(basename $REALIZATION_RESOURCES_PATH)
    fi

    # Look for weights file
    WEIGHTS_PATH=$(find "$DATASTREAM_RESOURCES" -type f -name "*weights*")
    NWEIGHT=$(find "$DATASTREAM_RESOURCES" -type f -name "*weights*" | wc -l)
    if [ ${NWEIGHT} -gt 1 ]; then
        echo "At most one weight file is allowed in "$DATASTREAM_RESOURCES
    fi

    # Look for geopackage file
    GEOPACKAGE_RESOURCES_PATH=$(find "$DATASTREAM_RESOURCES_NGENCONF_PATH" -type f -name "*.gpkg")
    NGEO=$(find "$DATASTREAM_RESOURCES_NGENCONF_PATH" -type f -name "*.gpkg" | wc -l)
    if [ ${NGEO} -gt 1 ]; then
        echo "At most one geopackage is allowed in "$DATASTREAM_RESOURCES_NGENCONF_PATH
    fi
    if [ ${NGEO} -gt 0 ]; then
        echo "Using" $GEOPACKAGE_RESOURCES_PATH
        GEO_BASE=$(basename $GEOPACKAGE_RESOURCES_PATH)
    else
        echo "geopackage missing from resources"     
        exit 1   
    fi

    # Look for geopackage attributes file
    # HACK: Should look for this in another way. Right now, this is the only parquet, but seems dangerous
    GEOPACKAGE_ATTR_RESOURCES_PATH=$(find "$DATASTREAM_RESOURCES_NGENCONF_PATH" -type f -name "*.parquet")        
    NATTR=$(find "$DATASTREAM_RESOURCES_NGENCONF_PATH" -type f -name "*.parquet" | wc -l)
    if [ ${NATTR} -gt 1 ]; then
        echo "At most one geopackage attributes is allowed in "$DATASTREAM_RESOURCES_NGENCONF_PATH
    fi
    if [ ${NATTR} -gt 0 ]; then
        echo "Using" $GEOPACKAGE_ATTR_RESOURCES_PATH
        GEO_ATTR_BASE=$(basename $GEOPACKAGE_ATTR_RESOURCES_PATH)
    else
        echo "geopackage attributes missing from resources"
        exit 1
    fi

    # Look for partitions file
    PARTITION_RESOURCES_PATH=$(find "$DATASTREAM_RESOURCES" -type f -name "partitions")
    if [ -e "$PARTITION_RESOURCES_PATH" ]; then
        PARTITION_NGENRUN_PATH=$NGEN_RUN_PATH/$(basename $PARTITION_RESOURCES_PATH)
        echo "Found $PARTITION_RESOURCES_PATH, copying to $PARTITION_NGENRUN_PATH"
        cp $PARTITION_RESOURCES_PATH $PARTITION_NGENRUN_PATH
    fi

    # Untar ngen bmi module configs    
    if [ -f "$NGEN_BMI_CONFS" ]; then
        echo "Using" $NGEN_BMI_CONFS
        tar -xf $NGEN_BMI_CONFS -C "${NGEN_CONFIG_PATH%/}"
        IGNORE_BMI=("PET,CFE")
    fi     

else
    echo "RESOURCE_PATH not provided, using cli args"

    if [ ! -z $REALIZATION ]; then
        REAL_BASE=$(basename $REALIZATION)
        REALIZATION_RESOURCES_PATH="$DATASTREAM_RESOURCES_NGENCONF_PATH$REAL_BASE"
        get_file "$REALIZATION" $REALIZATION_RESOURCES_PATH        
    else
        echo "realization arg is required"
        exit 1
    fi

    WEIGHTS_PATH=""

    if [ ! -z $SUBSET_ID ]; then
        echo "aquiring geospatial data from hfsubset"
    else
        if [ ! -z $GEOPACKAGE ]; then
            GEO_BASE=$(basename $GEOPACKAGE)
            GEOPACKAGE_RESOURCES_PATH="$DATASTREAM_RESOURCES_NGENCONF_PATH/$GEO_BASE"
            get_file "$GEOPACKAGE" $GEOPACKAGE_RESOURCES_PATH            
        else
            echo "geopackage arg is required"
            exit 1
        fi

        if [ ! -z $GEOPACKAGE_ATTR ]; then
            GEO_ATTR_BASE=$(basename $GEOPACKAGE_ATTR)
            GEOPACKAGE_ATTR_RESOURCES_PATH="$DATASTREAM_RESOURCES_NGENCONF_PATH/$GEO_ATTR_BASE"
            get_file "$GEOPACKAGE_ATTR" $GEOPACKAGE_ATTR_RESOURCES_PATH            
        else
            echo "geopackage attributes arg is required"
            exit 1
        fi   
    fi
fi

# copy files from resources into ngen-run
REALIZATION_NGENRUN_PATH=$NGEN_CONFIG_PATH/"realization.json"
cp $REALIZATION_RESOURCES_PATH $REALIZATION_NGENRUN_PATH
GEOPACKAGE_NGENRUN_PATH=$NGEN_CONFIG_PATH/"datastream.gpkg"
cp $GEOPACKAGE_RESOURCES_PATH $GEOPACKAGE_NGENRUN_PATH
GEOPACKAGE_ATTR_NGENRUN_PATH=$NGEN_CONFIG_PATH/$GEO_ATTR_BASE
cp $GEOPACKAGE_ATTR_RESOURCES_PATH $GEOPACKAGE_ATTR_NGENRUN_PATH
if [ -z "$DOMAIN_NAME" ]; then
    DOMAIN_NAME=${GEO_BASE%".gpkg"}
fi
log_time "GET_RESOURCES_END" $DATASTREAM_PROFILING

# begin calculations
if [ -e "$WEIGHTS_PATH" ]; then
    echo "Using $WEIGHTS_PATH"
    if [[ $(basename $WEIGHTS_PATH) != "weights.json" ]]; then
        echo "renaming $(basename $WEIGHTS_PATH) to weights.json" 
        mv "$WEIGHTS_PATH" ""$DATASTREAM_RESOURCES"/weights.json"
    fi
else
    log_time "WEIGHTS_START" $DATASTREAM_PROFILING
    echo "Weights file not found. Creating from" $GEO_BASE
    GEO_PATH_DOCKER=""$DOCKER_RESOURCES"/ngen-configs/$GEO_BASE"
    WEIGHTS_DOCKER=""$DOCKER_RESOURCES"/weights.json"
    docker run -v "$DATA_PATH:"$DOCKER_MOUNT"" \
        -u $(id -u):$(id -g) \
        -w "$DOCKER_MOUNT" forcingprocessor \
        python "$DOCKER_FP_PATH"weights_parq2json.py \
        --gpkg $GEO_PATH_DOCKER --outname $WEIGHTS_DOCKER --nprocs $NPROCS
    log_time "WEIGHTS_END" $DATASTREAM_PROFILING
fi

if [ ! -z $FORCINGS_TAR ]; then
    NWMURL_CONF_PATH="FORCINGS_TAR"
fi

log_time "DATASTREAMCONFGEN_START" $DATASTREAM_PROFILING
DOCKER_TAG="datastream:latest"
echo "Generating ngen-datastream metadata"
CONFIGURER="/ngen-datastream/python/src/datastream/configure-datastream.py"
docker run --rm -v "$DATA_PATH":"$DOCKER_MOUNT" $DOCKER_TAG \
    python $CONFIGURER \
    --docker_mount $DOCKER_MOUNT --start_date "$START_DATE" --end_date "$END_DATE" --data_path "$DATA_PATH" --resource_path "$RESOURCE_PATH" --gpkg "$GEOPACKAGE_RESOURCES_PATH" --gpkg_attr "$GEOPACKAGE_ATTR_RESOURCES_PATH" --subset_id_type "$SUBSET_ID_TYPE" --subset_id "$SUBSET_ID" --hydrofabric_version "$HYDROFABRIC_VERSION" --nwmurl_file "$NWMURL_CONF_PATH" --nprocs "$NPROCS" --domain_name "$DOMAIN_NAME" --host_type "$HOST_TYPE" --host_os "$HOST_OS"
log_time "DATASTREAMCONFGEN_END" $DATASTREAM_PROFILING


log_time "NGENCONFGEN_START" $DATASTREAM_PROFILING
# Look for pkl file
PKL_NAME="noah-owp-modular-init.namelist.input.pkl"
PKL_FILE=$(find "$NGEN_CONFIG_PATH" -type f -name $PKL_NAME)
if [ ! -f "$PKL_FILE" ]; then
    echo "Generating noah-owp pickle file"
    NOAHOWPPKL_GENERATOR="/ngen-datastream/python/src/datastream/noahowp_pkl.py"
    docker run --rm -v "$NGEN_RUN_PATH":"$DOCKER_MOUNT" $DOCKER_TAG \
        python $NOAHOWPPKL_GENERATOR \
        --hf_lnk_file "$DOCKER_MOUNT/config/$GEO_ATTR_BASE" --outdir $DOCKER_MOUNT"/config"   
fi

echo "Generating NGEN configs"
NGEN_CONFGEN="/ngen-datastream/python/src/datastream/ngen_configs_gen.py"
docker run --rm -v "$NGEN_RUN_PATH":"$DOCKER_MOUNT" $DOCKER_TAG \
    python $NGEN_CONFGEN \
    --hf_file "$DOCKER_MOUNT/config/datastream.gpkg" --hf_lnk_file $DOCKER_MOUNT/config/$GEO_ATTR_BASE --outdir "$DOCKER_MOUNT/config" --pkl_file "$DOCKER_MOUNT/config"/$PKL_NAME --realization "$DOCKER_MOUNT/config/realization.json" --ignore "$IGNORE_BMI"
log_time "NGENCONFGEN_END" $DATASTREAM_PROFILING    


if [ ! -z $FORCINGS_TAR ]; then
    log_time "GET_FORCINGS_START" $DATASTREAM_PROFILING
    echo "Using $FORCINGS_TAR"
    FORCINGS_BASE=$(basename $FORCINGS_TAR)    
    mkdir -p $NGEN_FORCINGS_PATH
    get_file "$FORCINGS_TAR" "./$FORCINGS_BASE"
    tar -xf $FORCINGS_BASE -C "${NGEN_FORCINGS_PATH%/}"
    rm "./$FORCINGS_BASE"
    log_time "GET_FORCINGS_END" $DATASTREAM_PROFILING
else
    log_time "FORCINGPROCESSOR_START" $DATASTREAM_PROFILING
    echo "Creating nwm filenames file"
    DOCKER_TAG="forcingprocessor:latest"
    docker run --rm -v "$DATA_PATH:"$DOCKER_MOUNT"" \
        -u $(id -u):$(id -g) \
        -w "$DOCKER_RESOURCES" $DOCKER_TAG \
        python "$DOCKER_FP_PATH"nwm_filenames_generator.py \
        "$DOCKER_MOUNT"/datastream-metadata/conf_nwmurl.json
    cp $DATASTREAM_RESOURCES/*filenamelist* $DATASTREAM_META_PATH/filenamelist.txt
    echo "Creating forcing files"
    docker run --rm -v "$DATA_PATH:"$DOCKER_MOUNT"" \
        -u $(id -u):$(id -g) \
        -w "$DOCKER_RESOURCES" $DOCKER_TAG \
        python "$DOCKER_FP_PATH"forcingprocessor.py "$DOCKER_META"/conf_fp.json
    log_time "FORCINGPROCESSOR_END" $DATASTREAM_PROFILING
fi    

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

cp -r $NGEN_RUN_PATH/*partitions* $DATASTREAM_RESOURCES/

echo "$NGEN_RUN_PATH"/*.csv | xargs mv -t $NGEN_OUTPUT_PATH --

log_time "MERKLE_START" $DATASTREAM_PROFILING
docker run --rm -v "$DATA_PATH":"$DOCKER_MOUNT" zwills/merkdir /merkdir/merkdir gen -o $DOCKER_MOUNT/merkdir.file $DOCKER_MOUNT
log_time "MERKLE_END" $DATASTREAM_PROFILING


log_time "TAR_START" $DATASTREAM_PROFILING
TAR_NAME="ngen-bmi-configs.tar.gz"
NGENCON_TAR_PATH="${DATASTREAM_RESOURCES_NGENCONF_PATH%/}/$TAR_NAME"
tar -cf - --exclude="*noah-owp-modular-init-cat*.namelist.input" --exclude="*realization*" --exclude="*.gpkg" --exclude="*.parquet" -C $NGEN_CONFIG_PATH . | pigz > $NGENCON_TAR_PATH

TAR_NAME="ngen-run.tar.gz"
NGENRUN_TAR_PATH="${DATA_PATH%/}/$TAR_NAME"
tar -cf - $NGEN_RUN_PATH | pigz > $NGENRUN_TAR_PATH
log_time "TAR_END" $DATASTREAM_PROFILING

log_time "DATASTREAM_END" $DATASTREAM_PROFILING

if [ -e "$S3_OUT" ]; then
    log_time "S3_MOVE_START" $DATASTREAM_PROFILING
    cp $NGENRUN_TAR_PATH $S3_OUT
    cp $DATA_PATH/merkdir.file $S3_OUT
    cp -r $DATASTREAM_META_PATH $S3_OUT
    cp -r $DATASTREAM_RESOURCES $S3_OUT
    echo "Data exists here: $S3_OUT"
    log_time "S3_MOVE_END" $DATASTREAM_PROFILING
fi
echo "Data exists here: $DATA_PATH"


echo "ngen-datastream run complete! Goodbye!"

    