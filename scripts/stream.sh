#!/bin/bash
set -e

SCRIPT_DIR=$(dirname "$(realpath "$0")")
PACAKGE_DIR=$(dirname $SCRIPT_DIR)
START_TIME=$(env TZ=US/Eastern date +'%Y%m%d%H%M%S')

is_s3_key() {
  [[ "$1" =~ ^s3:// ]]
}
is_tarball() {
  [[ "$1" =~ \.tar\.gz$ || "$1" =~ \.tgz$ || "$1" =~ \.tar$ ]]
}
is_netcdf() {
  [[ "$1" =~ \.nc$ ]]
}
is_directory() {
  [[ -d "$1" ]]
}
is_url() {
  [[ "$1" =~ ^(https?|ftp):// ]]
}
is_file() {
  [[ -e "$1" ]]
}

get_file() {
    local IN_STRING="$1"
    local OUT_STRING="$2"
    
    IN_STRING_BASE=$(basename $IN_STRING)
    echo "Retrieving "$IN_STRING" and storing it here "$OUT_STRING
    if is_directory "$IN_STRING"; then
        cp -r $IN_STRING/* $OUT_STRING
    elif is_s3_key "$IN_STRING"; then
        OUTPUT=$(aws s3 ls $IN_STRING)
        NUM_LINES=$(echo "$OUTPUT" | wc -l)
        if [ $NUM_LINES -eq 0 ]; then
            echo "Nothing found for $IN_STRING"
        elif [ $NUM_LINES -eq 1 ]; then
            aws s3 cp "$IN_STRING" "$(pwd)/$IN_STRING_BASE"
            get_file "$(pwd)/$IN_STRING_BASE" $OUT_STRING
            rm "$(pwd)/$IN_STRING_BASE"
        else
            aws s3 --recursive $IN_STRING $OUT_STRING
        fi 
    elif is_tarball "$IN_STRING"; then
        tar --use-compress-program=pigz -xf $IN_STRING -C "${OUT_STRING%/}"
    elif is_netcdf "$IN_STRING"; then
        cp $IN_STRING $OUT_STRING
    elif is_url "$IN_STRING"; then
        curl -# -L -o "$OUT_STRING" "$IN_STRING"
    elif is_file "$IN_STRING"; then
        cp $IN_STRING $OUT_STRING        
    else
        echo "ngen-datastream doesn't know how to deal with $IN_STRING"
    fi
}

is_in_list() {
  local var="$1"
  shift
  local list=("$@")
  for item in "${list[@]}"; do
    if [[ "$item" == "$var" ]]; then
      return 0
    fi
  done
  return 1
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
    echo "  -c, --CONF_FILE           <Path to datastream configuration file> "  
    echo "or run with cli args"
    echo "  -s, --START_DATE          <YYYYMMDDHHMM or \"DAILY\"> "
    echo "  -e, --END_DATE            <YYYYMMDDHHMM> "
    echo "  -C, --FORCING_SOURCE      <Forcing source option> "
    echo "  -D, --DOMAIN_NAME         <Name for spatial domain> "    
    echo "  -g, --GEOPACKAGE          <Path to geopackage file> "
    echo "  -I, --SUBSET_ID           <Hydrofabric id to subset>  "
    echo "  -i, --SUBSET_ID_TYPE      <Hydrofabric id type>  "   
    echo "  -v, --HYDROFABRIC_VERSION <Hydrofabric version> "      
    echo "  -R, --REALIZATION         <Path to realization file> "  
    echo "  -d, --DATA_DIR            <Path to write to> "
    echo "  -r, --RESOURCE_DIR        <Path to resource directory> "
    echo "  -f, --NWM_FORCINGS_DIR    <Path to nwm forcings directory> "
    echo "  -F, --NGEN_FORCINGS       <Path to ngen forcings directory, tarball, or netcdf> "
    echo "  -N, --NGEN_BMI_CONFS      <Path to ngen BMI config directory> "
    echo "  -S, --S3_BUCKET           <s3 bucket to write output to>  "
    echo "  -o, --S3_PREFIX           <File prefix within s3 bucket> "
    echo "  -n, --NPROCS              <Process limit> "
    echo "  -y, --DRYRUN              <True to skip calculations> "
    exit 1
}

# init variables
CONF_FILE=""
START_DATE=""
END_DATE=""
FORCING_SOURCE="NWM_RETRO_V3"
DOMAIN_NAME=""
GEOPACKAGE=""
SUBSET_ID=""
SUBSET_ID_TYPE=""
HYDROFABRIC_VERSION=""
REALIZATION=""
DATA_DIR=""
RESOURCE_DIR=""
NWM_FORCINGS_DIR=""
NGEN_FORCINGS=""
NGEN_BMI_CONFS=""
S3_BUCKET=""
S3_PREFIX=""
NPROCS=4
DRYRUN="False"

PKL_FILE=""
DATASTREAM_WEIGHTS=""

FORCING_SOURCE_OPTIONS=("NWM_RETRO_V2" "NWM_RETRO_V3" "NWM_OPERATIONAL_V3" "NOMADS_OPERATIONAL")
if is_in_list "$FORCING_SOURCE" "${FORCING_SOURCE_OPTIONS[@]}"; then
  :
else
  echo "FORCING_SOURCE $FORCING_SOURCE not among options: $FORCING_SOURCE_OPTIONS"
fi

# if ! command -v ec2-metadata >/dev/null 2>&1; then
#     HOST_TYPE="NON-AWS"
# else
#     HOST_TYPE=$(ec2-metadata --instance-type)
#     HOST_TYPE=$(echo "$HOST_TYPE" | awk -F': ' '{print $2}')
# fi
# echo "HOST_TYPE" $HOST_TYPE
if [ -f "/etc/os-release" ]; then
    HOST_OS=$(cat /etc/os-release | grep "PRETTY_NAME")
    HOST_OS=$(echo "$HOST_OS" | sed 's/.*"\(.*\)"/\1/')
else 
    echo "Warning: /etc/os-release file not found"
fi
echo "HOST_OS" $HOST_OS

PLATORM_TAG=""
if [ $(uname -m) = "x86_64" ]; then
    PLATORM_TAG="-x86"
elif [ $(uname -m) = "arm64" ]; then
    PLATORM_TAG=""
else 
  echo "Warning: Unsupported architecture $(uname -m)"
fi

# read cli args
while [ "$#" -gt 0 ]; do
    case "$1" in
        -c|--CONF_FILE) CONF_FILE="$2"; shift 2;;    
        -s|--START_DATE) START_DATE="$2"; shift 2;;
        -e|--END_DATE) END_DATE="$2"; shift 2;;
        -C|--FORCING_SOURCE) FORCING_SOURCE="$2"; shift 2;;
        -D|--DOMAIN_NAME) DOMAIN_NAME="$2"; shift 2;;
        -g|--GEOPACKAGE) GEOPACKAGE="$2"; shift 2;;
        -I|--SUBSET_ID) SUBSET_ID="$2"; shift 2;;
        -i|--SUBSET_ID_TYPE) SUBSET_ID_TYPE="$2"; shift 2;;
        -v|--HYDROFABRIC_VERSION) HYDROFABRIC_VERSION="$2"; shift 2;;        
        -R|--REALIZATION) REALIZATION="$2"; shift 2;;
        -d|--DATA_DIR) DATA_DIR="$2"; shift 2;;
        -r|--RESOURCE_DIR) RESOURCE_DIR="$2"; shift 2;;
        -f|--NWM_FORCINGS_DIR) NWM_FORCINGS_DIR="$2"; shift 2;;
        -F|--NGEN_FORCINGS) NGEN_FORCINGS="$2"; shift 2;;
        -N|--NGEN_BMI_CONFS) NGEN_BMI_CONFS="$2"; shift 2;;
        -S|--S3_BUCKET) S3_BUCKET="$2"; shift 2;;
        -o|--S3_PREFIX) S3_PREFIX="$2"; shift 2;;
        -n|--NPROCS) NPROCS="$2"; shift 2;;
        -y|--DRYRUN) DRYRUN="$2"; shift 2;;
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

if [ -e "$DATA_DIR" ]; then
    echo "The path $DATA_DIR exists. Please delete it or set a different path."
    exit 1
fi

mkdir -p $DATA_DIR
NGEN_RUN="${DATA_DIR%/}/ngen-run"

DATASTREAM_META="${DATA_DIR%/}/datastream-metadata"
DATASTREAM_RESOURCES="${DATA_DIR%/}/datastream-resources"
DATASTREAM_RESOURCES_NGENCONF="${DATASTREAM_RESOURCES%/}/config/"
DATASTREAM_RESOURCES_NWMFORCINGS="${DATASTREAM_RESOURCES%/}/nwm-forcings/"
DATASTREAM_RESOURCES_NGENFORCINGS="${DATASTREAM_RESOURCES%/}/ngen-forcings/"
DATASTREAM_PROFILING="${DATASTREAM_META%/}/profile.txt"
mkdir -p $DATASTREAM_RESOURCES
mkdir -p $DATASTREAM_META
touch $DATASTREAM_PROFILING
echo "DATASTREAM_START: $START_TIME" > $DATASTREAM_PROFILING

NGENRUN_CONFIG="${NGEN_RUN%/}/config"
NGENRUN_FORCINGS="${NGEN_RUN%/}/forcings"
NGENRUN_OUTPUT="${NGEN_RUN%/}/outputs"
NGENRUN_METADATA="${NGEN_RUN%/}/metadata"
NGENRUN_OUTPUT_NGEN="${NGEN_RUN%/}/outputs/ngen"
NGENRUN_OUTPUT_PARQUET="${NGEN_RUN%/}/outputs/parquet"
NGENRUN_OUTPUT_TROUTE="${NGEN_RUN%/}/outputs/troute"
NGENRUN_RESTART="${NGEN_RUN%/}/restart"
NGENRUN_LAKEOUT="${NGEN_RUN%/}/lakeout"
mkdir -p $NGENRUN_CONFIG
mkdir -p $NGENRUN_FORCINGS
mkdir -p $NGENRUN_OUTPUT
mkdir -p $NGENRUN_OUTPUT_NGEN
mkdir -p $NGENRUN_OUTPUT_PARQUET
mkdir -p $NGENRUN_OUTPUT_TROUTE
mkdir -p $NGENRUN_RESTART
mkdir -p $NGENRUN_LAKEOUT

DOCKER_DIR="$(dirname "${SCRIPT_DIR%/}")/docker"
DOCKER_MOUNT="/mounted_dir"
DOCKER_RESOURCES="${DOCKER_MOUNT%/}/datastream-resources"
DOCKER_META="${DOCKER_MOUNT%/}/datastream-metadata"
DOCKER_FP="/ngen-datastream/forcingprocessor/src/forcingprocessor/"
DOCKER_PY="/ngen-datastream/python_tools/src/python_tools/"

log_time "GET_RESOURCES_START" $DATASTREAM_PROFILING
if [ ! -z $RESOURCE_DIR ]; then
    echo "running in lite mode"
    get_file "$RESOURCE_DIR" $DATASTREAM_RESOURCES
else
    echo "running in standard mode"    
    mkdir -p $DATASTREAM_RESOURCES_NGENCONF
fi  

if [ ! -z $RESOURCE_DIR ]; then  

    # Untar ngen bmi module configs    
    if [ -f "$NGEN_BMI_CONFS" ]; then
        echo "Using" $NGEN_BMI_CONFS
        tar -xf $NGEN_BMI_CONFS -C "${NGENRUN_CONFIG%/}"
    fi    

    # Look for realization
    if [ -z $REALIZATION ]; then
        REALIZATION_RESOURCES=$(find "$DATASTREAM_RESOURCES_NGENCONF" -type f -name "*realization*.json")
        if [ -z $REALIZATION_RESOURCES ]; then
            echo "realization arg is required if not providing within the resource directory"
            exit 1
        else
            REAL_BASE=$(basename $REALIZATION_RESOURCES)                        
        fi
    else
        REAL_BASE=$(basename $REALIZATION)
        REALIZATION_RESOURCES="$DATASTREAM_RESOURCES_NGENCONF$REAL_BASE"
        get_file "$REALIZATION" $REALIZATION_RESOURCES   
    fi

    # Look for geopackage file
    if [ -z $GEOPACKAGE ]; then
        GEOPACKAGE_RESOURCES=$(find "$DATASTREAM_RESOURCES_NGENCONF" -type f -name "*.gpkg")
        NGEO=$(find "$DATASTREAM_RESOURCES_NGENCONF" -type f -name "*.gpkg" | wc -l)
        if [ ${NGEO} -gt 1 ]; then
            echo "At most one geopackage is allowed in "$DATASTREAM_RESOURCES_NGENCONF
            exit 1
        fi
        if [ ${NGEO} -gt 0 ]; then
            echo "Using" $GEOPACKAGE_RESOURCES
            GEO_BASE=$(basename $GEOPACKAGE_RESOURCES)
        else
            echo "geopackage missing from resources"     
            exit 1   
        fi    
    else
        GEO_BASE=$(basename $GEOPACKAGE)
        GEOPACKAGE_RESOURCES="$DATASTREAM_RESOURCES_NGENCONF/$GEO_BASE"
        get_file $GEOPACKAGE $GEOPACKAGE_RESOURCES
        NGEO=1
    fi

    # Look for nwm forcings
    if [ -z $NWM_FORCINGS_DIR ]; then
        NWM_FORCINGS_DIR=$(find $DATASTREAM_RESOURCES -type d -name "nwm-forcings")
        NNWM_FORCINGS_DIR=$(find $DATASTREAM_RESOURCES -type d -name "nwm-forcings" | wc -l)
        if [ ${NNWM_FORCINGS_DIR} -gt 0 ]; then
            NWM_FORCINGS=$(find "$DATASTREAM_RESOURCES_NWMFORCINGS" -type f -name "*.nc")
        fi
    fi

    # Look for ngen forcings
    if [ -z $NGEN_FORCINGS ]; then
        NNGEN_FORCINGS_DIR=$(find $DATASTREAM_RESOURCES -type d -name "ngen-forcings" | wc -l)
        if [ ${NNGEN_FORCINGS_DIR} -gt 0 ]; then
            NGEN_FORCINGS=$(find $DATASTREAM_RESOURCES_NGENFORCINGS -type f -name "forcings.")
        fi
    fi 

    # Look for partitions file
    PARTITION_RESOURCES=$(find "$DATASTREAM_RESOURCES_NGENCONF" -type f -name "*partitions*.json")
    if [ -e "$PARTITION_RESOURCES" ]; then
        PARTITION_NGENRUN=$NGEN_RUN/$(basename $PARTITION_RESOURCES)
        echo "Found $PARTITION_RESOURCES, copying to $PARTITION_NGENRUN"
        cp $PARTITION_RESOURCES $PARTITION_NGENRUN
    fi    

else
    echo "RESOURCE_DIR not provided, using cli args"

    if [ ! -z $REALIZATION ]; then
        REAL_BASE=$(basename $REALIZATION)
        REALIZATION_RESOURCES="$DATASTREAM_RESOURCES_NGENCONF$REAL_BASE"
        get_file "$REALIZATION" $REALIZATION_RESOURCES        
    else
        echo "realization arg is required"
        exit 1
    fi    

    # ngen bmi module configs    
    if [ ! -z "$NGEN_BMI_CONFS" ]; then
        echo "Using" $NGEN_BMI_CONFS
        cp -r "$NGEN_BMI_CONFS"/* $NGENRUN_CONFIG
    fi  

    # Look for nwm forcings
    if [ ! -z $NWM_FORCINGS_DIR ]; then
        NWM_FORCINGS=$(find "$NWM_FORCINGS_DIR" -type f -name "*.nc")
    fi    

    if [ ! -z $SUBSET_ID ]; then
        echo "aquiring geospatial data from hfsubset"        
    else
        if [ ! -z $GEOPACKAGE ]; then
            GEO_BASE=$(basename $GEOPACKAGE)
            GEOPACKAGE_RESOURCES="$DATASTREAM_RESOURCES_NGENCONF/$GEO_BASE"
            get_file "$GEOPACKAGE" $GEOPACKAGE_RESOURCES            
        else
            echo "geopackage arg is required"
            exit 1
        fi
    fi
fi

if [ ! -z $SUBSET_ID ]; then
    log_time "SUBSET_START" $DATASTREAM_PROFILING
    GEO_BASE="$SUBSET_ID.gpkg"
    GEOPACKAGE_RESOURCES="${DATASTREAM_RESOURCES_NGENCONF%/}/$GEO_BASE"
    hfsubset -w "medium_range" -s 'nextgen' -v "2.1.1" -l divides,flowlines,network,nexus,forcing-weights,flowpath-attributes,model-attributes -o $GEOPACKAGE_RESOURCES -t $SUBSET_ID_TYPE "$SUBSET_ID"
    GEOPACKAGE_NGENRUN=$NGENRUN_CONFIG/$GEO_BASE
    cp $GEOPACKAGE_RESOURCES $GEOPACKAGE_NGENRUN        
    log_time "SUBSET_END" $DATASTREAM_PROFILING
fi 

# copy files from resources into ngen-run
REALIZATION_NGENRUN=$NGENRUN_CONFIG/"realization.json"
cp $REALIZATION_RESOURCES $REALIZATION_NGENRUN
GEOPACKAGE_NGENRUN=$NGENRUN_CONFIG/$GEO_BASE
cp $GEOPACKAGE_RESOURCES $GEOPACKAGE_NGENRUN
if [ -z "$DOMAIN_NAME" ]; then
    DOMAIN_NAME=${GEO_BASE%".gpkg"}
fi
log_time "GET_RESOURCES_END" $DATASTREAM_PROFILING

# begin calculations
log_time "DATASTREAMCONFGEN_START" $DATASTREAM_PROFILING
DOCKER_TAG="awiciroh/datastream:latest$PLATORM_TAG"
echo "Generating ngen-datastream metadata"
CONFIGURER=$DOCKER_PY"configure_datastream.py"
docker run --rm -v "$DATA_DIR":"$DOCKER_MOUNT" $DOCKER_TAG \
    python3 $CONFIGURER \
    --docker_mount $DOCKER_MOUNT --start_date "$START_DATE" --end_date "$END_DATE" --data_path "$DATA_DIR" --forcings "$NGEN_FORCINGS" --forcing_source "$FORCING_SOURCE" --resource_path "$RESOURCE_DIR" --gpkg "$GEOPACKAGE_RESOURCES" --subset_id_type "$SUBSET_ID_TYPE" --subset_id "$SUBSET_ID" --hydrofabric_version "$HYDROFABRIC_VERSION" --nprocs "$NPROCS" --domain_name "$DOMAIN_NAME" --host_os "$HOST_OS" --host_os "$HOST_OS" --realization_file "${DOCKER_MOUNT}/ngen-run/config/realization.json"
log_time "DATASTREAMCONFGEN_END" $DATASTREAM_PROFILING

log_time "NGENCONFGEN_START" $DATASTREAM_PROFILING
# Look for pkl file
PKL_NAME="noah-owp-modular-init.namelist.input.pkl"
PKL_FILE=$(find "$NGENRUN_CONFIG" -type f -name $PKL_NAME)
if [ ! -f "$PKL_FILE" ]; then
    echo "Generating noah-owp pickle file"
    NOAHOWPPKL_GENERATOR=$DOCKER_PY"noahowp_pkl.py"
    if [ "$DRYRUN" == "True" ]; then
        echo "DRYRUN - NOAH PKL CALCULATION SKIPPED"
        echo "COMMAND: docker run --rm -v "$NGEN_RUN":"$DOCKER_MOUNT" $DOCKER_TAG \
            python3 $NOAHOWPPKL_GENERATOR \
            --hf_file "$DOCKER_MOUNT/config/$GEO_BASE" --outdir $DOCKER_MOUNT"/config""
    else
        docker run --rm -v "$NGEN_RUN":"$DOCKER_MOUNT" $DOCKER_TAG \
            python3 $NOAHOWPPKL_GENERATOR \
            --hf_file "$DOCKER_MOUNT/config/$GEO_BASE" --outdir $DOCKER_MOUNT"/config"
    fi
fi

echo "Generating NGEN configs"
NGEN_CONFGEN=$DOCKER_PY"ngen_configs_gen.py"
if [ "$DRYRUN" == "True" ]; then
    echo "DRYRUN - NGEN BMI CONFIGURATION FILE CREATION SKIPPED"
    echo "COMMAND: docker run --rm -v "$NGEN_RUN":"$DOCKER_MOUNT" \
        -u $(id -u):$(id -g) \
        $DOCKER_TAG python3 $NGEN_CONFGEN \
        --hf_file "$DOCKER_MOUNT/config/$GEO_BASE" --outdir "$DOCKER_MOUNT/config" --pkl_file "$DOCKER_MOUNT/config"/$PKL_NAME --realization "$DOCKER_MOUNT/config/realization.json""
else
    docker run --rm -v "$NGEN_RUN":"$DOCKER_MOUNT" \
        -u $(id -u):$(id -g) \
        $DOCKER_TAG python3 $NGEN_CONFGEN \
        --hf_file "$DOCKER_MOUNT/config/$GEO_BASE" --outdir "$DOCKER_MOUNT/config" --pkl_file "$DOCKER_MOUNT/config"/$PKL_NAME --realization "$DOCKER_MOUNT/config/realization.json"
    TAR_NAME="ngen-bmi-configs.tar.gz"
    NGENCON_TAR="${DATASTREAM_RESOURCES_NGENCONF%/}/$TAR_NAME"
    tar -cf - --exclude="*noah-owp-modular-init-cat*.namelist.input" --exclude="*realization*" --exclude="*.gpkg" --exclude="*.parquet" -C $NGENRUN_CONFIG . | pigz > $NGENCON_TAR
fi
log_time "NGENCONFGEN_END" $DATASTREAM_PROFILING    

if [ ! -z $NGEN_FORCINGS ]; then
    log_time "GET_FORCINGS_START" $DATASTREAM_PROFILING
    echo "Using $NGEN_FORCINGS"
    FORCINGS_BASE=$(basename $NGEN_FORCINGS)    
    get_file "$NGEN_FORCINGS" "$NGENRUN_FORCINGS"
    log_time "GET_FORCINGS_END" $DATASTREAM_PROFILING
else
    log_time "FORCINGPROCESSOR_START" $DATASTREAM_PROFILING
    echo "Creating nwm filenames file"
    DOCKER_TAG="awiciroh/forcingprocessor:latest$PLATORM_TAG"
    if [ ! -z $NWM_FORCINGS_DIR ]; then
        LOCAL_FILENAMES="filenamelist.txt"
        > "$LOCAL_FILENAMES"
        for file in $NWM_FORCINGS; do
            echo "$file"
        done | sort >> "$LOCAL_FILENAMES"
        cp $LOCAL_FILENAMES $DATASTREAM_META/filenamelist_local.txt
        rm $LOCAL_FILENAMES

        FILENAMES="filenamelist.txt"
        > "$FILENAMES"
        for file in $NWM_FORCINGS; do
            echo "$file"
        done | sort | while read -r file; do
            filebase=$(basename $file)
            echo "$DOCKER_RESOURCES/nwm-forcings/$filebase" >> "$FILENAMES"
        done
        cp $LOCAL_FILENAMES $DATASTREAM_META/filenamelist.txt
        rm $FILENAMES
        
        if [ ! -e $DATASTREAM_RESOURCES_NWMFORCINGS ]; then
            mkdir -p $DATASTREAM_RESOURCES_NWMFORCINGS
            echo "Copying nwm files into "$DATASTREAM_RESOURCES_NWMFORCINGS
            cp -r $NWM_FORCINGS_DIR/* $DATASTREAM_RESOURCES_NWMFORCINGS
        fi
    else
        docker run --rm -v "$DATA_DIR:"$DOCKER_MOUNT"" \
            -u $(id -u):$(id -g) \
            -w "$DOCKER_RESOURCES" $DOCKER_TAG \
            python3 "$DOCKER_FP"nwm_filenames_generator.py \
            "$DOCKER_MOUNT"/datastream-metadata/conf_nwmurl.json
        mv $DATASTREAM_RESOURCES/*filenamelist*.txt $DATASTREAM_META
    fi
    echo "Creating forcing files"
    if [ "$DRYRUN" == "True" ]; then
        echo "DRYRUN - FORCINGPROCESSOR SKIPPED"
        echo "COMMAND: docker run --rm -v "$DATA_DIR:"$DOCKER_MOUNT"" \
            -u $(id -u):$(id -g) \
            -w "$DOCKER_RESOURCES" $DOCKER_TAG \
            python3 "$DOCKER_FP"processor.py "$DOCKER_META"/conf_fp.json"
    else
        docker run --rm -v "$DATA_DIR:"$DOCKER_MOUNT"" \
            -u $(id -u):$(id -g) \
            -w "$DOCKER_RESOURCES" $DOCKER_TAG \
            python3 "$DOCKER_FP"processor.py "$DOCKER_META"/conf_fp.json
        mv $DATASTREAM_RESOURCES/profile_fp.txt $DATASTREAM_META 
        log_time "FORCINGPROCESSOR_END" $DATASTREAM_PROFILING
        if [ ! -e $$DATASTREAM_RESOURCES_NGENFORCINGS ]; then
            mkdir -p $DATASTREAM_RESOURCES_NGENFORCINGS
        fi
        cp $NGEN_RUN/forcings/*forcings* $DATASTREAM_RESOURCES_NGENFORCINGS
        mv $NGENRUN_METADATA $DATASTREAM_META
    fi
fi    

log_time "VALIDATION_START" $DATASTREAM_PROFILING
VALIDATOR=$DOCKER_PY"run_validator.py"
DOCKER_TAG="awiciroh/datastream:latest$PLATORM_TAG"
echo "Validating " $NGEN_RUN
if [ "$DRYRUN" == "True" ]; then
    echo "DRYRUN - VALIDATION SKIPPED"
    echo "COMMAND: docker run --rm -v "$NGEN_RUN":"$DOCKER_MOUNT" \
        $DOCKER_TAG python3 $VALIDATOR \
        --data_dir $DOCKER_MOUNT"
else
    docker run --rm -v "$NGEN_RUN":"$DOCKER_MOUNT" \
        $DOCKER_TAG python3 $VALIDATOR \
        --data_dir $DOCKER_MOUNT
fi
log_time "VALIDATION_END" $DATASTREAM_PROFILING

log_time "NGEN_START" $DATASTREAM_PROFILING
echo "Running NextGen in AUTO MODE from CIROH-UA/NGIAB-CloudInfra"
if [ "$DRYRUN" == "True" ]; then
    echo "DRYRUN - NEXTGEN EXECUTION SKIPPED"
    echo "COMMAND: docker run --rm -v "$NGEN_RUN":"$DOCKER_MOUNT" awiciroh/ciroh-ngen-image:latest$PLATORM_TAG "$DOCKER_MOUNT" auto $NPROCS"
else
    docker run --rm -v "$NGEN_RUN":"$DOCKER_MOUNT" awiciroh/ciroh-ngen-image:latest$PLATORM_TAG "$DOCKER_MOUNT" auto $NPROCS
    cp -r $NGEN_RUN/*partitions* $DATASTREAM_RESOURCES_NGENCONF/
fi
log_time "NGEN_END" $DATASTREAM_PROFILING

log_time "MERKLE_START" $DATASTREAM_PROFILING
if [ "$DRYRUN" == "True" ]; then
    echo "DRYRUN - MERKDIR EXECUTION SKIPPED"
    echo "COMMAND: docker run --rm -v "$DATA_DIR":"$DOCKER_MOUNT" zwills/merkdir /merkdir/merkdir gen -o $DOCKER_MOUNT/merkdir.file $DOCKER_MOUNT"
else
    docker run --rm -v "$DATA_DIR":"$DOCKER_MOUNT" zwills/merkdir /merkdir/merkdir gen -o $DOCKER_MOUNT/merkdir.file $DOCKER_MOUNT
fi
log_time "MERKLE_END" $DATASTREAM_PROFILING

log_time "TAR_START" $DATASTREAM_PROFILING
TAR_NAME="ngen-run.tar.gz"
NGENRUN_TAR="${DATA_DIR%/}/$TAR_NAME"
tar -cf - $NGEN_RUN | pigz > $NGENRUN_TAR
log_time "TAR_END" $DATASTREAM_PROFILING

log_time "DATASTREAM_END" $DATASTREAM_PROFILING

if [ -n "$S3_BUCKET" ]; then
    log_time "S3_MOVE_START" $DATASTREAM_PROFILING

    echo "Writing data to S3" $S3_OUT $S3_BUCKET $S3_PREFIX 

    S3_OUT="s3://$S3_BUCKET/${S3_PREFIX%/}/$TAR_NAME"
    aws s3 cp $NGENRUN_TAR $S3_OUT

    S3_OUT="s3://$S3_BUCKET/${S3_PREFIX%/}/merkdir.file"
    aws s3 cp $DATA_DIR/merkdir.file $S3_OUT

    S3_OUT="s3://$S3_BUCKET/${S3_PREFIX%/}/datastream-metadata"
    aws s3 sync $DATASTREAM_META $S3_OUT

    S3_OUT="s3://$S3_BUCKET/${S3_PREFIX%/}/datastream-resources"
    aws s3 sync $DATASTREAM_RESOURCES $S3_OUT

    echo "Data exists here: $S3_OUT"
    log_time "S3_MOVE_END" $DATASTREAM_PROFILING
fi
echo "Data exists here: $DATA_DIR"

echo "ngen-datastream run complete! Goodbye!"

    
