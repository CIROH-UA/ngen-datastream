import boto3
import time

client_ec2 = boto3.client('ec2')
client_ssm = boto3.client('ssm')
        
def get_command_result(command_id,instance_id):
    for j in range(200):
        try:
            output = client_ssm.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
                )
            if output['Status'] in ['Success', 'Failed', 'Canceled']:
                print(f'Command has completed -> {output}')
        except:
            print(f'waiting for command to finish...')
            time.sleep(4)

    return output

def lambda_handler(event, context):
    """
    Generic Poller funcion    
    """

    command_id  = event['command_id']
    instance_id = event['instance_parameters']['InstanceId']
    output = get_command_result(command_id,instance_id)

    ii_pass = False
    if output['Status'] == 'Success':
        print(f'Command has succeeded!')
        ii_pass = True
    elif output['Status'] == 'InProgress':
        ii_pass = False        
    else:
        raise Exception(f'Command failed {output}')
        ii_pass = False
    
    event['ii_pass'] = ii_pass
    return event
    
