import boto3
import time

client_s3  = boto3.client('s3')
        
def wait_for_object_existence(bucket_name,object_key):
                
    iters = 0
    max_iters = 10
    while True:
        try:
            client_s3.head_object(Bucket=bucket_name, Key=object_key)
            print(f"Key: '{object_key}' found!")
            break
        except:
            time.sleep(1)
            iters += 1
            if iters > max_iters: 
                print(f'FAILED')
                break
        
def lambda_handler(event, context):
    
    bucket  = event['bucket']
    obj_key = event['obj_key']
    wait_for_object_existence(bucket, obj_key)
    
    print(f'{obj_key} exists! Success!')
    return event
    
