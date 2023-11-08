import boto3
import time

client_ec2 = boto3.client('ec2')
client_ssm = boto3.client('ssm')
        
def get_command_result(command_id,instance_id):
    command_completed = False
    while not command_completed:
        try:
            output = client_ssm.get_command_invocation(
             CommandId=command_id,
                InstanceId=instance_id,
              )
            if output['Status'] in ['Success', 'Failed', 'Canceled']:
                print(f'Command has completed -> {output}')
                command_completed = True
        except:
            print(f'waiting for command to finish...')
            time.sleep(1)

    return output

def lambda_handler(event, context):
    """
    Generic Poller funcion    
    """

    command_id  = event['command_id']
    instance_id = event['instance_parameters']['InstanceId']
    output = get_command_result(command_id,instance_id)

    if output['Status'] == 'Success':
        print(f'Command has succeeded!')
    else:
        raise Exception(f'Command has failed!!!\n{command_id} {output}')
    
    return event
    
