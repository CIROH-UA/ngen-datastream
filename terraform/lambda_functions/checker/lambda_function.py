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
    
    bucket  = event['bucket']
    obj_key = event['obj_key']
    wait_for_object_existence(bucket, obj_key)
    
    return event
    
