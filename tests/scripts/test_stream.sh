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

rm -rf "${DATASTREAM_PATH}/data/stream_test"

# Operational
"${DATASTREAM_PATH}/scripts/stream.sh" -s "${DATE}0100" -e "${DATE}0100" -g https://lynker-spatial.s3.amazonaws.com/v20.1/gpkg/nextgen_09.gpkg -G https://lynker-spatial.s3.amazonaws.com/v20.1/model_attributes/nextgen_09.parquet -d "${DATASTREAM_PATH}/data/stream_test" -R /home/jlaser/code/CIROH/ngen-datastream/configs/ngen/realization_cfe_sloth_pet_nom.json -r s3://ngen-datastream/resources/v20.1/VPU_09/
rm -rf "${DATASTREAM_PATH}/data/stream_test"

# need update from nwmurl
# Retrospective
# "${DATASTREAM_PATH}/scripts/stream.sh" -s 202001200100 -e 202001200100 -g https://lynker-spatial.s3.amazonaws.com/v20.1/gpkg/nextgen_09.gpkg -G https://lynker-spatial.s3.amazonaws.com/v20.1/model_attributes/nextgen_09.parquet -d "${DATASTREAM_PATH}/data/stream_test" -R /home/jlaser/code/CIROH/ngen-datastream/configs/ngen/realization_cfe_sloth_pet_nom.json -r s3://ngen-datastream/resources/v20.1/VPU_09/
# rm -rf "${DATASTREAM_PATH}/data/stream_test"

# No resources, with forcings tar
"${DATASTREAM_PATH}/scripts/stream.sh" -s 202404200100 -e 202404200100 -g https://lynker-spatial.s3.amazonaws.com/v20.1/gpkg/nextgen_09.gpkg -G https://lynker-spatial.s3.amazonaws.com/v20.1/model_attributes/nextgen_09.parquet -d "${DATASTREAM_PATH}/data/stream_test" -R /home/jlaser/code/CIROH/ngen-datastream/configs/ngen/realization_cfe_sloth_pet_nom.json -f s3://ngen-datastream/test/forcings_09.tar.gz
rm -rf "${DATASTREAM_PATH}/data/stream_test"

# DAILY
"${DATASTREAM_PATH}/scripts/stream.sh" -s DAILY -e "${DATE}0100" -g https://lynker-spatial.s3.amazonaws.com/v20.1/gpkg/nextgen_09.gpkg -G https://lynker-spatial.s3.amazonaws.com/v20.1/model_attributes/nextgen_09.parquet -d "${DATASTREAM_PATH}/data/stream_test" -R /home/jlaser/code/CIROH/ngen-datastream/configs/ngen/realization_cfe_sloth_pet_nom.json -r s3://ngen-datastream/resources/v20.1/VPU_09/
rm -rf "${DATASTREAM_PATH}/data/stream_test"