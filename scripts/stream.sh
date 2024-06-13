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
        BUCKET=$(echo "$FILE" | cut -d '/' -f 3)
        KEY=$(echo "$FILE" | cut -d '/' -f 4-)
        if [[ "$KEY" == */ ]]; then
            aws s3 sync "$FILE" "$OUTFILE"
        else
            aws s3 cp "$FILE" "$OUTFILE"
        fi
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
    echo "  -c, --CONF_FILE           <Path to datastream configuration file> "  
    echo "or run with cli args"
    echo "  -s, --START_DATE          <YYYYMMDDHHMM or \"DAILY\"> "
    echo "  -e, --END_DATE            <YYYYMMDDHHMM> "
    echo "  -D, --DOMAIN_NAME         <Name for spatial domain> "    
    echo "  -g, --GEOPACKAGE          <Path to geopackage file> "
    echo "  -G, --GEOPACKAGE_ATTR     <Path to geopackage attributes file> " 
    echo "  -w, --HYDROFABRIC_WEIGHTS <Path to hydrofabric weights parquet> "  
    echo "  -I, --SUBSET_ID           <Hydrofabric id to subset>  "
    echo "  -i, --SUBSET_ID_TYPE      <Hydrofabric id type>  "   
    echo "  -v, --HYDROFABRIC_VERSION <Hydrofabric version> "      
    echo "  -R, --REALIZATION         <Path to realization file> "  
    echo "  -d, --DATA_DIR            <Path to write to> "
    echo "  -r, --RESOURCE_DIR        <Path to resource directory> "
    echo "  -f, --NWM_FORCINGS_DIR    <Path to nwm forcings directory> "
    echo "  -F, --NGEN_FORCINGS       <Path to ngen forcings tarball> "
    echo "  -S, --S3_MOUNT            <Path to mount s3 bucket to>  "
    echo "  -o, --S3_PREFIX           <File prefix within s3 mount>"
    echo "  -n, --NPROCS              <Process limit> "
    exit 1
}

# init variables
CONF_FILE=""
START_DATE=""
END_DATE=""
DOMAIN_NAME=""
GEOPACKAGE=""
GEOPACKAGE_ATTR=""
HYDROFABRIC_WEIGHTS=""
SUBSET_ID=""
SUBSET_ID_TYPE=""
HYDROFABRIC_VERSION=""
REALIZATION=""
DATA_DIR=""
RESOURCE_DIR=""
NWM_FORCINGS_DIR=""
NGEN_FORCINGS=""
S3_MOUNT=""
S3_PREFIX=""
NPROCS=4

PKL_FILE=""
DATASTREAM_WEIGHTS=""

# BROKEN
# if ! command -v ec2-metadata >/dev/null 2>&1; then
#     HOST_TYPE="NON-AWS"
# else
#     HOST_TYPE=$(ec2-metadata --instance-type)
#     HOST_TYPE=$(echo "$HOST_TYPE" | awk -F': ' '{print $2}')
# fi
# echo "HOST_TYPE" $HOST_TYPE
# if [ -f "/etc/os-release" ]; then
#     HOST_OS=$(cat /etc/os-release | grep "PRETTY_NAME")
#     HOST_OS=$(echo "$HOST_OS" | sed 's/.*"\(.*\)"/\1/')
# else 
#     echo "Warning: /etc/os-release file not found"
# fi
# echo "HOST_OS" $HOST_OS

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
        -D|--DOMAIN_NAME) DOMAIN_NAME="$2"; shift 2;;
        -g|--GEOPACKAGE) GEOPACKAGE="$2"; shift 2;;
        -G|--GEOPACKAGE_ATTR) GEOPACKAGE_ATTR="$2"; shift 2;;
        -w|--HYDROFABRIC_WEIGHTS) HYDROFABRIC_WEIGHTS="$2"; shift 2;;
        -I|--SUBSET_ID) SUBSET_ID="$2"; shift 2;;
        -i|--SUBSET_ID_TYPE) SUBSET_ID_TYPE="$2"; shift 2;;
        -v|--HYDROFABRIC_VERSION) HYDROFABRIC_VERSION="$2"; shift 2;;        
        -R|--REALIZATION) REALIZATION="$2"; shift 2;;
        -d|--DATA_DIR) DATA_DIR="$2"; shift 2;;
        -r|--RESOURCE_DIR) RESOURCE_DIR="$2"; shift 2;;
        -f|--NWM_FORCINGS_DIR) NWM_FORCINGS_DIR="$2"; shift 2;;
        -F|--NGEN_FORCINGS) NGEN_FORCINGS="$2"; shift 2;;
        -S|--S3_MOUNT) S3_MOUNT="$2"; shift 2;;
        -o|--S3_PREFIX) S3_PREFIX="$2"; shift 2;;
        -n|--NPROCS) NPROCS="$2"; shift 2;;
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
        if [[ -z "$DATA_DIR" ]]; then
            DATA_DIR="${PACAKGE_DIR%/}/data/$DATE"
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
        if [[ -z "$DATA_DIR" ]]; then
            DATA_DIR="${PACAKGE_DIR%/}/data/${END_DATE::-4}"
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
    if [[ -z "${DATA_DIR}" ]]; then
        DATA_DIR="${PACAKGE_DIR%/}/data/$START_DATE-$END_DATE"
    fi
    if [[ -n "${S3_MOUNT}" ]]; then
        S3_OUT="$S3_MOUNT$S3_PREFIX"
        echo "S3_OUT: " $S3_OUT
        mkdir -p $S3_OUT
    fi
fi

# create directories
if [ -e "$DATA_DIR" ]; then
    echo "The path $DATA_DIR exists. Please delete it or set a different path."
    exit 1
fi

mkdir -p $DATA_DIR
NGEN_RUN="${DATA_DIR%/}/ngen-run"

DATASTREAM_META="${DATA_DIR%/}/datastream-metadata"
DATASTREAM_RESOURCES="${DATA_DIR%/}/datastream-resources"
DATASTREAM_RESOURCES_NGENCONF="${DATASTREAM_RESOURCES%/}/config/"
DATASTREAM_RESOURCES_HYDROFABRIC="${DATASTREAM_RESOURCES%/}/hydrofabric/"
DATASTREAM_RESOURCES_NWMFORCINGS="${DATASTREAM_RESOURCES%/}/nwm-forcings/"
DATASTREAM_RESOURCES_NGENFORCINGS="${DATASTREAM_RESOURCES%/}/ngen-forcings/"
DATASTREAM_RESOURCES_DATASTREAM="${DATASTREAM_RESOURCES%/}/datastream/"
NGEN_BMI_CONFS="${DATASTREAM_RESOURCES_NGENCONF%/}/ngen-bmi-configs.tar.gz"
DATASTREAM_PROFILING="${DATASTREAM_META%/}/profile.txt"
mkdir -p $DATASTREAM_META
touch $DATASTREAM_PROFILING
echo "DATASTREAM_START: $START_TIME" > $DATASTREAM_PROFILING

NGENRUN_CONFIG="${NGEN_RUN%/}/config"
NGENRUN_FORCINGS="${NGEN_RUN%/}/forcings"
NGENRUN_OUTPUT="${NGEN_RUN%/}/outputs"
NGENRUN_OUTPUT_NGEN="${NGEN_RUN%/}/outputs/ngen"
NGENRUN_OUTPUT_PARQUET="${NGEN_RUN%/}/outputs/parquet"
NGENRUN_OUTPUT_TROUTE="${NGEN_RUN%/}/outputs/troute"
NGENRUN_RESTART="${NGEN_RUN%/}/restart"
NGENRUN_LAKEOUT="${NGEN_RUN%/}/lakeout"
mkdir -p $NGENRUN_CONFIG
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

log_time "GET_RESOURCES_START" $DATASTREAM_PROFILING
if [ ! -z $RESOURCE_DIR ]; then
    echo "running in lite mode"
    get_file "$RESOURCE_DIR" $DATASTREAM_RESOURCES
else
    echo "running in standard mode"
    mkdir -p $DATASTREAM_RESOURCES
    mkdir -p $DATASTREAM_RESOURCES_NGENCONF
fi

if [ ! -z $SUBSET_ID ]; then
    log_time "SUBSET_START" $DATASTREAM_PROFILING
    GEOPACKAGE="$SUBSET_ID.gpkg"
    GEOPACKAGE_RESOURCES="${DATASTREAM_RESOURCES%/}/$GEOPACKAGE"
    hfsubset -o $GEOPACKAGE_RESOURCES -r $HYDROFABRIC_VERSION -t $SUBSET_ID_TYPE $SUBSET_ID
    cp $GEOPACKAGE_RESOURCES $GEOPACKAGE_NGENRUN        
    log_time "SUBSET_END" $DATASTREAM_PROFILING
fi   

if [ ! -z $RESOURCE_DIR ]; then  

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

    # Untar ngen bmi module configs    
    if [ -f "$NGEN_BMI_CONFS" ]; then
        echo "Using" $NGEN_BMI_CONFS
        tar -xf $NGEN_BMI_CONFS -C "${NGENRUN_CONFIG%/}"

        # HACK: this should look search for which files exist and ignore those modules
        IGNORE_BMI=("PET,CFE")
    fi     

    # Look for geopackage file
    if [ -z $GEOPACKAGE ]; then
        GEOPACKAGE_RESOURCES=$(find "$DATASTREAM_RESOURCES_HYDROFABRIC" -type f -name "*.gpkg")
        NGEO=$(find "$DATASTREAM_RESOURCES_HYDROFABRIC" -type f -name "*.gpkg" | wc -l)
        if [ ${NGEO} -gt 1 ]; then
            echo "At most one geopackage is allowed in "$DATASTREAM_RESOURCES_HYDROFABRIC
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
        GEOPACKAGE_RESOURCES="$DATASTREAM_RESOURCES_HYDROFABRIC/$GEO_BASE"
        get_file $GEOPACKAGE $GEOPACKAGE_RESOURCES
        NGEO=1
    fi

    # Look for hydrofabric weights file
    HYDROFABRIC_WEIGHTS=$(find "$DATASTREAM_RESOURCES_HYDROFABRIC" -type f -name "*weights*.parquet")
    HYDROFABRIC_NWEIGHTS=$(find "$DATASTREAM_RESOURCES_HYDROFABRIC" -type f -name "*weights*.parquet" | wc -l)
    if [ ${HYDROFABRIC_NWEIGHTS} -gt 1 ]; then
        echo "At most one hydrofabric weight file is allowed in "$DATASTREAM_RESOURCES
        exit 1
    fi

    # HACK, remove when attributes files are renamed
    if [ ${HYDROFABRIC_NWEIGHTS} -gt 0 ]; then
        mv *weights*.parquet $DATASTREAM_RESOURCES
    fi

    # Look for geopackage attributes file
    # HACK: Should look for this in another way. Right now, this is the only parquet, but seems dangerous
    if [ -z $GEOPACKAGE_ATTR ]; then
        GEOPACKAGE_ATTR_RESOURCES=$(find "$DATASTREAM_RESOURCES_HYDROFABRIC" -type f -name "*.parquet")        
        NATTR=$(find "$DATASTREAM_RESOURCES_HYDROFABRIC" -type f -name "*.parquet" | wc -l)
        if [ ${NATTR} -gt 1 ]; then
            echo "At most one geopackage attributes is allowed in "$DATASTREAM_RESOURCES_HYDROFABRIC
            exit 1
        fi
        if [ ${NATTR} -gt 0 ]; then
            echo "Using" $GEOPACKAGE_ATTR_RESOURCES
            GEO_ATTR_BASE=$(basename $GEOPACKAGE_ATTR_RESOURCES)
        else
            echo "geopackage attributes missing from resources"
            exit 1
        fi
    else
        GEO_ATTR_BASE=$(basename $GEOPACKAGE_ATTR)
        GEOPACKAGE_ATTR_RESOURCES="$DATASTREAM_RESOURCES_HYDROFABRIC/$GEO_ATTR_BASE"
        get_file $GEOPACKAGE_ATTR $GEOPACKAGE_ATTR_RESOURCES
        NATTR=1
    fi

    # HACK, remove when attributes files are renamed
    if [ ${HYDROFABRIC_NWEIGHTS} -gt 0 ]; then
        mv $DATASTREAM_RESOURCES*weights*.parquet $DATASTREAM_RESOURCES_HYDROFABRIC
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
            NGEN_FORCINGS=$(find $DATASTREAM_RESOURCES_NGENFORCINGS -type f -name "forcings.tar.gz")
        fi
    fi

    # Look for weights file
    DATASTREAM_WEIGHTS=$(find "$DATASTREAM_RESOURCES_DATASTREAM" -type f -name "*weights*.json")
    NWEIGHT=$(find "$DATASTREAM_RESOURCES_DATASTREAM" -type f -name "*weights*.json" | wc -l)
    if [ ${NWEIGHT} -gt 1 ]; then
        echo "At most one datastream weight file is allowed in "$DATASTREAM_RESOURCES
        exit 1
    fi    

    # Look for partitions file
    PARTITION_RESOURCES=$(find "$DATASTREAM_RESOURCES_DATASTREAM" -type f -name "*partitions*.json")
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

    # Look for nwm forcings
    if [ ! -z $NWM_FORCINGS_DIR ]; then
        NWM_FORCINGS=$(find "$NWM_FORCINGS_DIR" -type f -name "*.nc")
    fi    

    if [ ! -z $SUBSET_ID ]; then
        echo "aquiring geospatial data from hfsubset"
    else
        mkdir -p $DATASTREAM_RESOURCES_HYDROFABRIC
        mkdir -p $DATASTREAM_RESOURCES_DATASTREAM
        if [ ! -z $GEOPACKAGE ]; then
            GEO_BASE=$(basename $GEOPACKAGE)
            GEOPACKAGE_RESOURCES="$DATASTREAM_RESOURCES_HYDROFABRIC/$GEO_BASE"
            get_file "$GEOPACKAGE" $GEOPACKAGE_RESOURCES            
        else
            echo "geopackage arg is required"
            exit 1
        fi

        if [ ! -z $GEOPACKAGE_ATTR ]; then
            GEO_ATTR_BASE=$(basename $GEOPACKAGE_ATTR)
            GEOPACKAGE_ATTR_RESOURCES="$DATASTREAM_RESOURCES_HYDROFABRIC/$GEO_ATTR_BASE"
            get_file "$GEOPACKAGE_ATTR" $GEOPACKAGE_ATTR_RESOURCES            
        else
            echo "geopackage attributes arg is required"
            exit 1
        fi   
    fi
fi

# copy files from resources into ngen-run
REALIZATION_NGENRUN=$NGENRUN_CONFIG/"realization.json"
cp $REALIZATION_RESOURCES $REALIZATION_NGENRUN
GEOPACKAGE_NGENRUN=$NGENRUN_CONFIG/$GEO_BASE
cp $GEOPACKAGE_RESOURCES $GEOPACKAGE_NGENRUN
GEOPACKAGE_ATTR_NGENRUN=$NGENRUN_CONFIG/$GEO_ATTR_BASE
cp $GEOPACKAGE_ATTR_RESOURCES $GEOPACKAGE_ATTR_NGENRUN
if [ -z "$DOMAIN_NAME" ]; then
    DOMAIN_NAME=${GEO_BASE%".gpkg"}
fi
log_time "GET_RESOURCES_END" $DATASTREAM_PROFILING

# begin calculations
if [ -z $NGEN_FORCINGS ]; then 
    if [ -e "$DATASTREAM_WEIGHTS" ]; then
        echo "Using $DATASTREAM_WEIGHTS"
        if [[ $(basename $DATASTREAM_WEIGHTS) != "weights.json" ]]; then
            echo "renaming $(basename $DATASTREAM_WEIGHTS) to weights.json" 
            mv "$DATASTREAM_WEIGHTS" ""$DATASTREAM_RESOURCES"/weights.json"
        fi
    else
        log_time "WEIGHTS_START" $DATASTREAM_PROFILING
        echo "Datastream weights file not found. Creating from" $GEO_BASE
        GEO_DOCKER=""$DOCKER_RESOURCES"/hydrofabric/$GEO_BASE"
        WEIGHTS_DOCKER=""$DOCKER_RESOURCES"/datastream/weights.json"
        DOCKER_TAG="awiciroh/forcingprocessor:latest$PLATORM_TAG"
        docker run -v "$DATA_DIR:"$DOCKER_MOUNT"" \
            -u $(id -u):$(id -g) \
            -w "$DOCKER_MOUNT" $DOCKER_TAG \
            python "$DOCKER_FP"weights_parq2json.py \
            --gpkg $GEO_DOCKER --outname $WEIGHTS_DOCKER --nprocs $NPROCS --weights_parquet "$HYDROFABRIC_WEIGHTS"
        log_time "WEIGHTS_END" $DATASTREAM_PROFILING
    fi
fi

log_time "DATASTREAMCONFGEN_START" $DATASTREAM_PROFILING
DOCKER_TAG="awiciroh/datastream:latest$PLATORM_TAG"
echo "Generating ngen-datastream metadata"
CONFIGURER="/ngen-datastream/python/src/datastream/configure-datastream.py"
docker run --rm -v "$DATA_DIR":"$DOCKER_MOUNT" $DOCKER_TAG \
    python $CONFIGURER \
    --docker_mount $DOCKER_MOUNT --start_date "$START_DATE" --end_date "$END_DATE" --data_path "$DATA_DIR" --forcings_tar "$NGEN_FORCINGS" --resource_path "$RESOURCE_DIR" --gpkg "$GEOPACKAGE_RESOURCES" --gpkg_attr "$GEOPACKAGE_ATTR_RESOURCES" --subset_id_type "$SUBSET_ID_TYPE" --subset_id "$SUBSET_ID" --hydrofabric_version "$HYDROFABRIC_VERSION" --nprocs "$NPROCS" --domain_name "$DOMAIN_NAME" --host_type "$HOST_TYPE" --host_os "$HOST_OS" --realization_file "${DOCKER_MOUNT}/ngen-run/config/realization.json"
log_time "DATASTREAMCONFGEN_END" $DATASTREAM_PROFILING

log_time "NGENCONFGEN_START" $DATASTREAM_PROFILING
# Look for pkl file
PKL_NAME="noah-owp-modular-init.namelist.input.pkl"
PKL_FILE=$(find "$NGENRUN_CONFIG" -type f -name $PKL_NAME)
if [ ! -f "$PKL_FILE" ]; then
    echo "Generating noah-owp pickle file"
    NOAHOWPPKL_GENERATOR="/ngen-datastream/python/src/datastream/noahowp_pkl.py"
    docker run --rm -v "$NGEN_RUN":"$DOCKER_MOUNT" $DOCKER_TAG \
        python $NOAHOWPPKL_GENERATOR \
        --hf_lnk_file "$DOCKER_MOUNT/config/$GEO_ATTR_BASE" --outdir $DOCKER_MOUNT"/config"   
fi

echo "Generating NGEN configs"
NGEN_CONFGEN="/ngen-datastream/python/src/datastream/ngen_configs_gen.py"
docker run --rm -v "$NGEN_RUN":"$DOCKER_MOUNT" \
    -u $(id -u):$(id -g) \
    $DOCKER_TAG python $NGEN_CONFGEN \
    --hf_file "$DOCKER_MOUNT/config/$GEO_BASE" --hf_lnk_file $DOCKER_MOUNT/config/$GEO_ATTR_BASE --outdir "$DOCKER_MOUNT/config" --pkl_file "$DOCKER_MOUNT/config"/$PKL_NAME --realization "$DOCKER_MOUNT/config/realization.json" --ignore "$IGNORE_BMI"
TAR_NAME="ngen-bmi-configs.tar.gz"
NGENCON_TAR="${DATASTREAM_RESOURCES_NGENCONF%/}/$TAR_NAME"
tar -cf - --exclude="*noah-owp-modular-init-cat*.namelist.input" --exclude="*realization*" --exclude="*.gpkg" --exclude="*.parquet" -C $NGENRUN_CONFIG . | pigz > $NGENCON_TAR
log_time "NGENCONFGEN_END" $DATASTREAM_PROFILING    

if [ ! -z $NGEN_FORCINGS ]; then
    log_time "GET_FORCINGS_START" $DATASTREAM_PROFILING
    echo "Using $NGEN_FORCINGS"
    FORCINGS_BASE=$(basename $NGEN_FORCINGS)    
    mkdir -p $NGENRUN_FORCINGS
    get_file "$NGEN_FORCINGS" "./$FORCINGS_BASE"
    tar --use-compress-program=pigz -xf $FORCINGS_BASE -C "${NGENRUN_FORCINGS%/}"
    rm "./$FORCINGS_BASE"
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
        cp $LOCAL_FILENAMES $DATASTREAM_META/filenamelist.txt
        rm $LOCAL_FILENAMES

        FILENAMES="filenamelist.txt"
        > "$FILENAMES"
        for file in $NWM_FORCINGS; do
            echo "$file"
        done | sort | while read -r file; do
            filebase=$(basename $file)
            echo "$DOCKER_RESOURCES/nwm-forcings/$filebase" >> "$FILENAMES"
        done
        
        if [ ! -e $DATASTREAM_RESOURCES_NWMFORCINGS ]; then
            mkdir -p $DATASTREAM_RESOURCES_NWMFORCINGS
            echo "Copying nwm files into "$DATASTREAM_RESOURCES_NWMFORCINGS
            cp -r $NWM_FORCINGS_DIR/* $DATASTREAM_RESOURCES_NWMFORCINGS
        fi
        mv $FILENAMES $DATASTREAM_RESOURCES_DATASTREAM
    else
        docker run --rm -v "$DATA_DIR:"$DOCKER_MOUNT"" \
            -u $(id -u):$(id -g) \
            -w "$DOCKER_RESOURCES" $DOCKER_TAG \
            python "$DOCKER_FP"nwm_filenames_generator.py \
            "$DOCKER_MOUNT"/datastream-metadata/conf_nwmurl.json
        cp $DATASTREAM_RESOURCES/*filenamelist*.txt $DATASTREAM_META
        mv $DATASTREAM_RESOURCES/*filenamelist*.txt $DATASTREAM_RESOURCES_DATASTREAM
    fi
    echo "Creating forcing files"
    docker run --rm -v "$DATA_DIR:"$DOCKER_MOUNT"" \
        -u $(id -u):$(id -g) \
        -w "$DOCKER_RESOURCES" $DOCKER_TAG \
        python "$DOCKER_FP"forcingprocessor.py "$DOCKER_META"/conf_fp.json
    mv $DATASTREAM_RESOURCES/log_fp.txt $DATASTREAM_META 
    log_time "FORCINGPROCESSOR_END" $DATASTREAM_PROFILING
    if [ ! -e $$DATASTREAM_RESOURCES_NGENFORCINGS ]; then
        mkdir -p $DATASTREAM_RESOURCES_NGENFORCINGS
    fi
    rm $DATASTREAM_RESOURCES_DATASTREAM*filenamelist*.txt
    mv $NGEN_RUN/forcings/*forcings.tar.gz $DATASTREAM_RESOURCES_NGENFORCINGS"forcings.tar.gz"
fi    

log_time "VALIDATION_START" $DATASTREAM_PROFILING
VALIDATOR="/ngen-datastream/python/src/datastream/run_validator.py"
DOCKER_TAG="awiciroh/datastream:latest$PLATORM_TAG"
echo "Validating " $NGEN_RUN
docker run --rm -v "$NGEN_RUN":"$DOCKER_MOUNT" \
    $DOCKER_TAG python $VALIDATOR \
    --data_dir $DOCKER_MOUNT
log_time "VALIDATION_END" $DATASTREAM_PROFILING

log_time "NGEN_START" $DATASTREAM_PROFILING
echo "Running NextGen in AUTO MODE from CIROH-UA/NGIAB-CloudInfra"
docker run --rm -v "$NGEN_RUN":"$DOCKER_MOUNT" awiciroh/ciroh-ngen-image:latest$PLATORM_TAG "$DOCKER_MOUNT" auto $NPROCS
log_time "NGEN_END" $DATASTREAM_PROFILING

cp -r $NGEN_RUN/*partitions* $DATASTREAM_RESOURCES_DATASTREAM/

log_time "MERKLE_START" $DATASTREAM_PROFILING
docker run --rm -v "$DATA_DIR":"$DOCKER_MOUNT" zwills/merkdir /merkdir/merkdir gen -o $DOCKER_MOUNT/merkdir.file $DOCKER_MOUNT
log_time "MERKLE_END" $DATASTREAM_PROFILING

log_time "TAR_START" $DATASTREAM_PROFILING
TAR_NAME="ngen-run.tar.gz"
NGENRUN_TAR="${DATA_DIR%/}/$TAR_NAME"
tar -cf - $NGEN_RUN | pigz > $NGENRUN_TAR
log_time "TAR_END" $DATASTREAM_PROFILING

log_time "DATASTREAM_END" $DATASTREAM_PROFILING

if [ -e "$S3_OUT" ]; then
    log_time "S3_MOVE_START" $DATASTREAM_PROFILING
    cp $NGENRUN_TAR $S3_OUT
    cp $DATA_DIR/merkdir.file $S3_OUT
    cp -r $DATASTREAM_META $S3_OUT
    cp -r $DATASTREAM_RESOURCES $S3_OUT
    echo "Data exists here: $S3_OUT"
    log_time "S3_MOVE_END" $DATASTREAM_PROFILING
fi
echo "Data exists here: $DATA_DIR"

echo "ngen-datastream run complete! Goodbye!"

    
