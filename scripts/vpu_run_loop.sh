#!/bin/bash
DATA_DIR="/home/ec2-user/ngen-datastream/data"
SCRIPT_DIR="/home/ec2-user/ngen-datastream/scripts"
RESOURCES_DIR="/home/ec2-user/local_resources"
MOUNT_DIR="/home/ec2-user/ngen-datastream/data/mount"
S3_BASE_URL="https://lynker-spatial.s3.amazonaws.com/v20.1"
DATE="20240321"
START_TIME="202403210000"
NUM_THREADS="8"

VPUs=("01" "02" "03N" "03S" "03W" "04" "05" "06" "07" "08" "09" "10L" "10U" "11" "12" "13" "14" "15" "16" "17" "18")
for vpu in "${VPUs[@]}"; do
    # command="rm -rf $DATA_DIR/$DATE && $SCRIPT_DIR/stream.sh -s DAILY -e $START_TIME -r $RESOURCES_DIR -S $MOUNT_DIR -o /daily/$DATE/VPU_${vpu} -g $S3_BASE_URL/gpkg/nextgen_${vpu}.gpkg -G $S3_BASE_URL/model_attributes/nextgen_${vpu}.parquet -D VPU_${vpu} -n $NUM_THREADS"
    # eval "$command"

    execution=
    aws stepfunctions start-execution --state-machine-arn $STATE_MACHINE_ARN --input file://$execution



done