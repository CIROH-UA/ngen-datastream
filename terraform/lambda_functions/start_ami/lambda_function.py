import boto3
import time
from datetime import datetime

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

def replace_in_dict(d,replacement):
    pattern = "$DATE"
    for key, value in d.items():
        if isinstance(value, dict):
            replace_in_dict(value)
        elif isinstance(value, str) and pattern in value:
            d[key] = value.replace(pattern, replacement)
        elif isinstance(value, list):
            for jelem in value:
                if isinstance(jelem, dict):
                    replace_in_dict(jelem)
                elif isinstance(jelem, str) and pattern in jelem:
                    d[key] = jelem.replace(pattern, replacement)
    
def lambda_handler(event, context):

    global client_ec2, client_ssm
    client_ec2 = boto3.client('ec2',event['region'])
    client_ssm = boto3.client('ssm',event['region'])    

    params             = event['instance_parameters']

    date = datetime.now()

    replace_in_dict(params,date.strftime('%Y%m%d') )

    response           = client_ec2.run_instances(**params)
    instance_id        = response['Instances'][0]['InstanceId']

    client_ec2.start_instances(InstanceIds=[instance_id])   
    if not wait_for_instance_status(instance_id, 'Online'):
        raise Exception(f"EC2 instance {instance_id} did not reach 'Online' state")
    print(f'{instance_id} has been launched and running')

    event['instance_parameters']['InstanceId']  = instance_id

    return event
