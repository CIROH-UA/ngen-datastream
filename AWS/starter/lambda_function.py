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
        time.sleep(1)
        retries += 1
    return False
    
def lambda_handler(event, context):
    
    instance_id = event['instance_id']
    client_ec2.start_instances(InstanceIds=[instance_id])   
    if not wait_for_instance_status(instance_id, 'Online'):
        raise Exception(f"EC2 instance {instance_id} did not reach 'Online' state")
    print(f'{instance_id} has been launched and running')

    return event
