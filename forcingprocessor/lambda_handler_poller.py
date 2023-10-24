import boto3
import json
import time

client_s3  = boto3.client('s3')
client_ec2 = boto3.client('ec2')
client_ssm = boto3.client('ssm')
        
def get_command_result(response,instance_id):
    iters = 0
    max_iters = 1000
    while True:
        try:
            command_id = response['Command']['CommandId']
            output = client_ssm.get_command_invocation(
             CommandId=command_id,
                InstanceId=instance_id,
              )
            if output['Status'] in ['Success', 'Failed', 'Canceled']:
                print(f'Command has completed -> {output}')
                return output
        except:
            print(f'waiting for command to finish...')
            time.sleep(1)
            iters += 1
            if iters > max_iters: 
                print(f'FAILED')    
                break        

def lambda_handler(event, context):
    """
    Handler function to kick off the NWM 2 NGEN forcingprocessor
    
    """

    response = event['input']['response']
    instance_id = event['input']['instance_id']
    output = get_command_result(response,instance_id)

    if output['Status'] == 'Success':
        print(f'Forcings have been processed! Shutting down processor {instance_id}')
        client_ec2.stop_instances(InstanceIds=[instance_id])
        print(f'Goodbye')
    else:
        raise Exception('Forcing processor failed!!!')
    
