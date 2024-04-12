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
OBJECT_KEY=""

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

file=$(find $EXEC_DIR -type f -name '*_fp.json')

echo "Executing state machine $SM_ARN with $file"
aws stepfunctions start-execution \
    --state-machine-arn $SM_ARN \
    --name $(env TZ=US/Eastern date +'%Y%m%d%H%M%S')\
    --input "file://"$file"" --region $REGION 

OBJECT_KEY=$(jq -r '.obj_key' "$file")
BUCKET=$(jq -r '.bucket' "$file")
OBJECT_KEY=$BUCKET/$OBJECT_KEY
echo "state machine executed, awaiting "$OBJECT_KEY" existence"

check_s3_object "$OBJECT_KEY"
exists=$?
while [ $exists -ne 0 ]; do
    echo "$OBJECT_KEY does not exist. Waiting for a minute and checking again" $(env TZ=US/Eastern date +'%Y%m%d%H%M%S')
    sleep 60
    check_s3_object "$OBJECT_KEY"
    exists=$?
done
echo "$OBJECT_KEY exists, launching next run in 10 seconds"    
sleep 10

for vpu in "${VPUs[@]}"; do
    file="execution_dailyrun_$vpu.json"
    
    echo "Executing state machine $SM_ARN with $file"
    aws stepfunctions start-execution \
        --state-machine-arn $SM_ARN \
        --name $(env TZ=US/Eastern date +'%Y%m%d%H%M%S')\
        --input "file://"$EXEC_DIR""$file"" --region $REGION 

    sleep 10
done
