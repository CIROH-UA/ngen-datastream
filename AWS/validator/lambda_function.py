import boto3
import time

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

    instance_id         = event['instance_parameters']['InstanceId']
    ngen_input_bucket   = event['bucket']
    ngen_input_key      = event['complete_tarball_key']

    command = f'source /home/ec2-user/ngen-cal-venv/bin/activate && python /home/ec2-user/ngen-cal/python/conf_validation.py --tarball' 
    response = client_ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': [command]}
    )
    wait_for_command_response(response,instance_id)

    event['command_id'] = response['Command']['CommandId']

    return event   