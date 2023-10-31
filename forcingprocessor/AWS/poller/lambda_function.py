import boto3
import time

client_ec2 = boto3.client('ec2')
client_ssm = boto3.client('ssm')
        
def get_command_result(command_id,instance_id):
    iters = 0
    max_iters = 1000
    while True:
        try:
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
    Generic Poller funcion    
    """

    command_id  = event['current_run']['command_id']
    instance_id = event['current_run']['instance_id']
    ii_shutdown = event['current_run']['shutdown']
    output = get_command_result(command_id,instance_id)

    if output['Status'] == 'Success':
        print(f'Command has succeded!')
        if ii_shutdown: 
            print(f'Shutting down processor {instance_id}')
            client_ec2.stop_instances(InstanceIds=[instance_id])
        else:
            print(f'{instance_id} remains running!')
        print(f'Goodbye')
    else:
        raise Exception(f'Command has failed!!!\n{command_id}')
    
    output = {}
    output['current_run'] = event['current_run']
    return output
    
