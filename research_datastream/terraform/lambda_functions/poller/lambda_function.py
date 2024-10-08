import boto3
import time

def get_command_result(command_id,instance_id):
    
    try:
        output = client_ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id,
            )
        if output['Status'] in ['Success', 'Failed', 'Canceled']:
            print(f'Command has completed -> {output}')
    except:
        output = None

    return output

def lambda_handler(event, context):
    """
    Generic Poller funcion    
    """

    global client_ssm, client_ec2
    client_ssm = boto3.client('ssm',region_name=event['region'])
    client_ec2 = boto3.client('ec2',region_name=event['region'])    

    command_id  = event['command_id']
    instance_id = event['instance_parameters']['InstanceId']
    output = get_command_result(command_id,instance_id)

    ii_pass = False
    while not ii_pass:
        output = get_command_result(command_id,instance_id)
        if output['Status'] == 'Success':
            print(f'Command has succeeded!')
            ii_pass = True
            break
        elif output['Status'] == 'InProgress':
            ii_pass = False   
            print(f'Commands are still in progress. Waiting a minute and checking again')
            time.sleep(10)                            
        else:
            raise Exception(f'Command failed {output}')         
    
    event['ii_pass'] = ii_pass
    return event
    
