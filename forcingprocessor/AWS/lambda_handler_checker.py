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
        except:
            time.sleep(1)
            iters += 1
            if iters > max_iters: 
                print(f'FAILED')
                break
        
def lambda_handler(event, context):
    """
    Handler function to kick off the NWM 2 NGEN forcingprocessor
    
    """
    
    bucket_name = 'ngenforcingdev'
    object_key  = 'automation_test/forcings/forcing.tar.gz'    
    wait_for_object_existence(bucket_name,object_key)
    
    print(f'forcing.tar.gz exists! Success! Exiting state machine')

    output = {"bucket":bucket_name,"key":object_key}

    return output
    
