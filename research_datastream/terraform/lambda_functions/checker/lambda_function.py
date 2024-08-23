import boto3
import time

client_s3  = boto3.client('s3')
        
def wait_for_object_existence(bucket_name,object_key):

    ii_obj_found = False  
    while not ii_obj_found:
        try:
            client_s3.head_object(Bucket=bucket_name, Key=object_key)
            print(f"Key: '{object_key}' found!")
            ii_obj_found = True
        except:
            time.sleep(1)
    if not ii_obj_found: raise Exception(f'{object_key} does not exist in {bucket_name} ')
        
def lambda_handler(event, context):
    
    if event["run_options"]['ii_check_s3']:
        if not 'datastream_command_options' in event: raise Exception(f'The lambda only knows how to check s3 object for datastream_command_options with s3_bucket and object_prefix set')
        bucket  = event['datastream_command_options']['s3_bucket']
        obj_key = event['datastream_command_options']['object_prefix'] + '/ngen-run.tar.gz'
        print(f'Checking if {obj_key} exists in {bucket}')
        wait_for_object_existence(bucket, obj_key)
    else:
        print(f'No s3 object check was performed.')
    
    return event
    
