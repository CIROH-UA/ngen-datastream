import boto3
import time
import re
import datetime
from datetime import timezone

client_s3  = boto3.client('s3')
        
def wait_for_object_existence(bucket_name,prefix):

    while True:
        response = client_s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        if 'Contents' in response:
            print(f"Objects exists in bucket {bucket_name} at prefix {prefix}")
            return
        else:
            time.sleep(1)
        
def lambda_handler(event, context):
    
    bucket = None
    prefix = None
    if event["run_options"]['ii_check_s3']:
        if not 'datastream_command_options' in event: 
            for jcmd in event["commands"]:
                bucket_pattern = r"--s3_bucket[=\s']+([^\s']+)"
                match = re.search(bucket_pattern, jcmd)
                if match: 
                    bucket = match.group(1)
                prefix_pattern = r"--s3_prefix[=\s']+([^\s']+)"
                match = re.search(prefix_pattern, jcmd)
                if match: 
                    prefix = match.group(1)                
        else:
            bucket  = event['datastream_command_options']['s3_bucket']
            prefix = event['datastream_command_options']['s3_prefix']
        if bucket is None or prefix is None:
            raise Exception(f'User specified ii_check_s3, but no s3_bucket or s3_prefix were not found in commands')
        if "DAILY" in prefix: 
            prefix = re.sub(r"\DAILY",datetime.datetime.now(timezone.utc).strftime('%Y%m%d'),prefix)
        print(f'Checking if any objects with prefix {prefix} exists in {bucket}')
        wait_for_object_existence(bucket, prefix)
    else:
        print(f'No s3 object check was performed.')
    
    return event

if __name__ == "__main__":

    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument('--execution', dest="execution", type=str, help="",default = None)
    args = parser.parse_args()

    with open(args.execution,'r') as fp:
        execution = json.load(fp)

    lambda_handler(execution,"")
    
    
