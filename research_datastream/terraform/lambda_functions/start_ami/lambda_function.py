import boto3
import time, os
from datetime import datetime

def wait_for_instance_status(instance_id, status, max_retries=100000):
    retries = 0
    while retries < max_retries:
        response = client_ec2.describe_instances(
           InstanceIds=[
               instance_id
           ]
        )
        if response['Reservations'][0]['Instances'][0]['State']['Name'] == "running":
            time.sleep(5)
            return True
        else:
            print(f"FAILED with response {response}")
        time.sleep(1)
        retries += 1
    return False

def replace_in_dict(d, pattern, replacement):
    for key, value in d.items():
        if isinstance(value, dict):
            replace_in_dict(value, pattern, replacement)
        elif isinstance(value, str) and pattern in value:
            d[key] = value.replace(pattern, replacement)
        elif isinstance(value, list):
            for jelem in value:
                if isinstance(jelem, dict):
                    replace_in_dict(jelem, pattern, replacement)
                elif isinstance(jelem, str) and pattern in jelem:
                    d[key] = jelem.replace(pattern, replacement)
    
def lambda_handler(event, context):

    t0 = time.time()
    event['t0'] = t0
    if not "timeout_s" in event['run_options']:
        print(f'Setting timeout_s to default 3600 seconds')
        event['run_options']['timeout_s'] = 3600

    event['region'] = os.environ['AWS_REGION']
    global client_ec2
    client_ec2 = boto3.client('ec2',region_name=event['region'])

    event['instance_parameters']['MaxCount'] = 1
    event['instance_parameters']['MinCount'] = 1
    params             = event['instance_parameters']

    date = datetime.now()
    date_fmt = date.strftime('%Y%m%d')
    replace_in_dict(params,"$DATE", date_fmt)
    replace_in_dict(params,"$INSTANCE_TYPE", params['InstanceType'])

    response           = client_ec2.run_instances(**params)
    print(response)
    instance_id        = response['Instances'][0]['InstanceId']

    while True:
        try:
            client_ec2.start_instances(InstanceIds=[instance_id])   
            break
        except:
            print(f'Tried running {instance_id}, failed. Trying again.')
            time.sleep(1)

    if not wait_for_instance_status(instance_id, 'Online'):
        raise Exception(f"EC2 instance {instance_id} did not reach 'Online' state")
    print(f'{instance_id} has been launched and running')

    event['instance_parameters']['InstanceId']  = instance_id

    return event