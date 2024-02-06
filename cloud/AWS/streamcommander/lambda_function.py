import boto3
import time
from datetime import datetime

client_s3  = boto3.client('s3')
client_ssm = boto3.client('ssm')

def wait_for_command_response(response,instance_id):
    iters = 0
    max_iters = 10
    while True:
        try:
            command_id = response['Command']['CommandId']
            output = client_ssm.get_command_invocation(
             CommandId=command_id,
                InstanceId=instance_id,
              )
            print(f'Response obtained -> {output}')
            break
        except:
            print(f'waiting for command response...')
            time.sleep(1)
            iters += 1
            if iters > max_iters: 
                print(f'FAILED')
                break

def lambda_handler(event, context):
    """
    Handler function to issue commands to an ec2
    
    """

    instance_id = event['instance_parameters']['InstanceId']

    response = client_ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': event['commands'],
                    "executionTimeout": [f"{3600*24}"]
                    }
    )
    wait_for_command_response(response,instance_id)
    print(f'{instance_id} is launched and processing forcings')

    event['command_id']  = response['Command']['CommandId']

    date = datetime.now()
    date_fmt = date.strftime('%Y%m%d')    
    if 'DATE' in event['obj_key']:
        key_str = event['obj_key']        
        event['obj_key'] = key_str.replace('DATE',date_fmt)        

    return event
