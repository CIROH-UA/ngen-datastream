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
    Handler function to poll the NWM 2 NGEN forcingprocessor
    
    """

    command_id = event['command_id']
    instance_id = event['instance_id']
    output = get_command_result(command_id,instance_id)

    if output['Status'] == 'Success':
        print(f'Forcings have been processed! Shutting down processor {instance_id}')
        client_ec2.stop_instances(InstanceIds=[instance_id])
        print(f'Goodbye')
    else:
        raise Exception('Forcing processor failed!!!')
    
