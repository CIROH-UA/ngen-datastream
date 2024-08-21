import boto3
import time

client_s3  = boto3.client('s3')
        
def wait_for_object_existence(bucket_name,object_key):
                
    while True:
        try:
            client_s3.head_object(Bucket=bucket_name, Key=object_key)
            print(f"Key: '{object_key}' found!")
            break
        except:
            time.sleep(1)
        
def lambda_handler(event, context):
    
    if event["run_options"]['ii_check_s3']:
        bucket  = event['bucket']
        obj_key = event['obj_key']
        print(f'Checking if {obj_key} exists in {bucket}')
        wait_for_object_existence(bucket, obj_key)
    else:
        print(f'No s3 object check was performed.')
    
    return event
    
