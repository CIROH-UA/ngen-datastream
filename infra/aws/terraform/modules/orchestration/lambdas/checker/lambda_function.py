import boto3
import time
import re
import datetime
from datetime import timezone
import json

client_s3  = boto3.client('s3')
        
def wait_for_object_existence(bucket_name,prefix):

    count = 0
    while count < 10:
        response = client_s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        if 'Contents' in response:
            print(f"Objects exists in bucket {bucket_name} at prefix {prefix}")
            return True
        else:
            count += 1
            time.sleep(1)
    return False

def lambda_handler(event, context):
    
    bucket = None
    prefix = None
    ii_ds_cmd = False
    if event["run_options"]['ii_check_s3']:

        if not 'datastream_command_options' in event: 
            for jcmd in event["commands"]:
                bucket_pattern = r"(?i)--s3_bucket[=\s']+([^\s']+)"
                match = re.search(bucket_pattern, jcmd)
                if match: 
                    bucket = match.group(1)
                prefix_pattern = r"(?i)--s3_prefix[=\s']+([^\s']+)"
                match = re.search(prefix_pattern, jcmd)
                if match: 
                    prefix = match.group(1)                        
                bucket_pattern = r"(?i)/scripts/datastream[=\s']+([^\s']+)"
                match = re.search(bucket_pattern, jcmd)
                if match: 
                    ii_ds_cmd = True                                
        else:
            bucket  = event['datastream_command_options']['s3_bucket']
            prefix = event['datastream_command_options']['s3_prefix']
        if bucket is None or prefix is None:
            raise Exception(f'User specified ii_check_s3, but no s3_bucket or s3_prefix were not found in commands')
            
        if ii_ds_cmd:
            prefix += "/ngen-run.tar.gz"
        else:
            prefix += "/metadata/forcings_metadata/metadata.csv"
        print(f'Checking if any objects with prefix {prefix} exists in {bucket}')
        if not wait_for_object_existence(bucket, prefix):
            store_failed_execution(event,bucket)
        else:
            event['ii_s3_object_checked'] = True
            print(f'Found s3 object with prefix {prefix} in {bucket}, proceeding with execution.')
            
    else:
        print(f'No s3 object check was performed.')
    
    return event

def store_failed_execution(execution,bucket):
    print(f'Execution failed, storing execution in {bucket}')
    timestamp = datetime.datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    key = f"test/cicd/nrds/failed_executions/{timestamp}.json"
    client_s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(execution))
    print(f'Execution stored in {bucket} at {key}')

if __name__ == "__main__":

    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument('--execution', dest="execution", type=str, help="",default = None)
    args = parser.parse_args()

    with open(args.execution,'r') as fp:
        execution = json.load(fp)

    lambda_handler(execution,"")
    
    
