#!/bin/bash
usage() {
    echo "Welcome to ngen-datastream-parallel, where many simultaneous ngen-datastream statemachine executions are created and issued to AWS." \
    echo "Usage: $0 [options]"
    echo "Either provide a datastream configuration file"
    echo "  -e, --EXEC_DIR   <Path to datastream statemachine execution file directory> "  
    echo "  -s, --SM_ARN     <AWS ARN to datastream statemachine> " 
    echo "  -r, --REGION     <AWS region> "  
    exit 1
}

EXEC_DIR=""
SM_ARN=""
REGION=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        -e|--EXEC_DIR) EXEC_DIR="$2"; shift 2;;
        -s|--SM_ARN) SM_ARN="$2"; shift 2;;
        -r|--REGION) REGION="$2"; shift 2;;
        *) usage;;
    esac
done

check_s3_object() {
    aws s3 ls "s3://$1" > /dev/null 2>&1
    return $?
}

exec_files=$(ls "$EXEC_DIR")
# VPUs=("02" "03N" "03S" "03W" "04" "14")      # 175189
# VPUs=("01" "05" "06" "07" "08" "09" "10L")   # 184435
# VPUs=("10U" "11" "12" "13" "14")             # 183157
# VPUs=("15" "16" "17" "18")                   # 194622
VPUs=("14" "18") 

for vpu in "${VPUs[@]}"; do
    file="execution_dailyrun_$vpu.json"
    
    echo "Executing state machine $SM_ARN with $file"
    aws stepfunctions start-execution \
        --state-machine-arn $SM_ARN \
        --name $(env TZ=US/Eastern date +'%Y%m%d%H%M%S')\
        --input "file://"$EXEC_DIR""$file"" --region $REGION 

    echo "state machine executed, awaiting key existence"
    object_key="ngen-datastream/daily/20240326/VPU_$vpu/ngen-run.tar.gz"
    
    check_s3_object "$object_key"
    exists=$?
    while [ $exists -ne 0 ]; do
        echo "$object_key does not exist. Waiting for a minute and checking again" $(env TZ=US/Eastern date +'%Y%m%d%H%M%S')
        sleep 60
        check_s3_object "$object_key"
        exists=$?
    done
    echo "key exists, launching next run in 5 seconds"
    sleep 5
done
