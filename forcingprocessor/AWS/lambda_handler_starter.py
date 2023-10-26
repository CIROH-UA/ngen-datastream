import boto3
import time

client_ec2 = boto3.client('ec2')
client_ssm = boto3.client('ssm')

def wait_for_instance_status(instance_id, status, max_retries=120):
    retries = 0
    while retries < max_retries:
        instance_info = client_ssm.describe_instance_information(
            InstanceInformationFilterList=[
                {
                    'key': 'InstanceIds',
                    'valueSet': [instance_id],
                },
            ]
        )
        if instance_info['InstanceInformationList'] and instance_info['InstanceInformationList'][0]['PingStatus'] == status:
            return True
        time.sleep(1)  # Wait for 10 seconds before checking again
        retries += 1
    return False
    
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
    Handler function to kick off the NWM 2 NGEN forcingprocessor
    
    """
    # Start the EC2 instance
    instance_id = 'i-066cb631f20ae0eb5'
    client_ec2.start_instances(InstanceIds=[instance_id])   
    if not wait_for_instance_status(instance_id, 'Online'):
        raise Exception(f"EC2 instance {instance_id} did not reach 'Online' state")

    command = 'source /home/ec2-user/venv/bin/activate && python /home/ec2-user/ngen-datastream/forcingprocessor/src/nwmforcing2ngen.py /home/ec2-user/ngen-datastream/forcingprocessor/src/conf.json' 
    response = client_ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': [command]}
    )
    wait_for_command_response(response,instance_id)
    print(f'{instance_id} is launched and processing forcings')
    
    output = {}
    output['command_id']  = response['Command']['CommandId']
    output['instance_id'] = instance_id
    return output
