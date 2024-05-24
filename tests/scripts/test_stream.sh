set -e
set -x

DATASTREAM_PATH=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        -d|--DATASTREAM_PATH) DATASTREAM_PATH="$2"; shift 2;;
        *) usage;;
    esac
done  

DATE=$(env TZ=US/Eastern date +'%Y%m%d')
RESOURCES="${DATASTREAM_PATH}/data/test_resources_$DATE"
START_OPERATIONAL="${DATE}0100"
END_OPERATIONAL="${DATE}0500"
DATA_DIR="${DATASTREAM_PATH}/data/stream_test"
LYNKER_SPATIAL="https://lynker-spatial.s3.amazonaws.com/hydrofabric/v20.1"
NPROCS=8
rm -rf $DATA_DIR
rm -rf $RESOURCES

echo "Operational without resources"
/bin/bash -x "${DATASTREAM_PATH}/scripts/stream.sh" -s $START_OPERATIONAL -e $END_OPERATIONAL -g $LYNKER_SPATIAL/gpkg/nextgen_09.gpkg -G $LYNKER_SPATIAL/model_attributes/nextgen_09.parquet -d $DATA_DIR -R "${DATASTREAM_PATH}/configs/ngen/realization_cfe_sloth_pet_nom.json" -n $NPROCS
mkdir -p $DATASTREAM_PATH/data/nwmurl
cp $DATA_DIR/datastream-metadata/filenamelist.txt $DATASTREAM_PATH/data/nwmurl
cp -r "${DATA_DIR}/datastream-resources" $RESOURCES
rm -rf $DATA_DIR

echo "Operational with resources"
/bin/bash -x "${DATASTREAM_PATH}/scripts/stream.sh" -s $START_OPERATIONAL -e $END_OPERATIONAL -d $DATA_DIR -r $RESOURCES -n $NPROCS
rm -rf $DATA_DIR

echo "Operational with resources, local geopackage and attrs"
mv $RESOURCES/hydrofabric/nextgen_09.gpkg $DATASTREAM_PATH/data
mv $RESOURCES/hydrofabric/nextgen_09.parquet $DATASTREAM_PATH/data
REALIZATION_RESOURCES=$(find "$RESOURCES/config" -type f -name "*realization*.json")
REAL_BASE=$(basename $REALIZATION_RESOURCES)
mv $RESOURCES/config/$REAL_BASE $DATASTREAM_PATH/data
/bin/bash -x "${DATASTREAM_PATH}/scripts/stream.sh" -s $START_OPERATIONAL -e $END_OPERATIONAL -d $DATA_DIR -r $RESOURCES -g $DATASTREAM_PATH/data/nextgen_09.gpkg -G $DATASTREAM_PATH/data/nextgen_09.parquet -R $DATASTREAM_PATH/data/$REAL_BASE -n $NPROCS
rm -rf $DATA_DIR

echo "Operational with resources without ngen-forcing tarball, without weights"
rm $RESOURCES/ngen-forcings/forcings.tar.gz
mv $DATASTREAM_PATH/data/nextgen_09.gpkg $RESOURCES/hydrofabric
mv $DATASTREAM_PATH/data/nextgen_09.parquet $RESOURCES/hydrofabric
mv $DATASTREAM_PATH/data/$REAL_BASE $RESOURCES/config
mv $RESOURCES/datastream/weights.json $DATASTREAM_PATH/data
/bin/bash -x "${DATASTREAM_PATH}/scripts/stream.sh" -s $START_OPERATIONAL -e $END_OPERATIONAL -d $DATA_DIR -r $RESOURCES -n $NPROCS
mkdir -p $RESOURCES/nwm-forcings
while IFS= read -r url; do
    filename=$(basename "$url")
    curl -o "$RESOURCES/nwm-forcings/$filename" "$url"
done < "$DATASTREAM_PATH/data/nwmurl/filenamelist.txt"
rm -rf $DATA_DIR

echo "Operational with resources with local nwm files"
mv $DATASTREAM_PATH/data/weights.json $RESOURCES/datastream/
/bin/bash -x "${DATASTREAM_PATH}/scripts/stream.sh" -s $START_OPERATIONAL -e $END_OPERATIONAL -d $DATA_DIR -r $RESOURCES -n $NPROCS

# need update from nwmurl
# Retrospective
# /bin/bash -x "${DATASTREAM_PATH}/scripts/stream.sh" -s 202001200100 -e 202001200100 -d "${DATASTREAM_PATH}/data/stream_test" -r $RESOURCES
# rm -rf "${DATASTREAM_PATH}/data/stream_test"

# DAILY
# /bin/bash -x "${DATASTREAM_PATH}/scripts/stream.sh" -s DAILY -e "${DATE}0100" -g $LYNKER_SPATIAL/gpkg/nextgen_09.gpkg -G $LYNKER_SPATIAL/model_attributes/nextgen_09.parquet -d $DATA_DIR -R "${DATASTREAM_PATH}/configs/ngen/realization_cfe_sloth_pet_nom.json" -n $NPROCS
# rm -rf "${DATASTREAM_PATH}/data/stream_test"

# Need tests for: manual hydrofabric subset, internal hfsubset call