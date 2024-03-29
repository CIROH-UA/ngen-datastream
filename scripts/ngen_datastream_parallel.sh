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

exec_files=$(ls "$EXEC_DIR")
for file in $exec_files
do
    echo "Executing state machine $SM_ARN with $file"
    aws stepfunctions start-execution \
        --state-machine-arn $SM_ARN \
        --name $(env TZ=US/Eastern date +'%Y%m%d%H%M%S')\
        --input "file://"$EXEC_DIR""$file"" --region $REGION 

    sleep 5
done
