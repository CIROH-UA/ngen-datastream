import boto3
import os, sys, time
from pathlib import Path

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

    instance_id         = event['current_run']['instance_id']
    ngen_input_bucket   = event['current_run']['bucket']
    ngen_input_key      = event['complete_tarball_key']

    command = f'source /home/ec2-user/ngen-cal-venv/bin/activate && python /home/ec2-user/ngen-cal/python/conf_validation.py --bucket {ngen_input_bucket} --key {ngen_input_key}' 
    response = client_ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': [command]}
    )
    wait_for_command_response(response,instance_id)

    event['current_run']['shutdown'] = True

    output = {}
    output['current_run'] = event['current_run']

    return output   