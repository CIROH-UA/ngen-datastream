import boto3
import json
import time
import datetime

client_s3  = boto3.client('s3')
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
            
def update_conf():

    conf_path = '/tmp/conf.json'
    bucket = 'ngenresourcesdev'
    client_s3.download_file(bucket, 'dailyrun_template_conf.json', conf_path)
    with open(conf_path,'r') as fp:
        data = json.load(fp)
        
    date = datetime.datetime.now()
    date = date.strftime('%Y%m%d')
    print(date)

    hourminute = '0000'
    
    data['forcing']['start_date'] = date + hourminute
    data['forcing']['end_date']   = date + hourminute
    
    prefix = f"dailyrun/{date}"
    data['storage']['output_bucket_path'] = prefix
    
    conf_daily = 'dailyrun.json'
    with open('/tmp/' + conf_daily,'w') as fp:
        json.dump(data,fp)
    client_s3.upload_file('/tmp/' + conf_daily, bucket, conf_daily)
    
    print(f'The daily run config has been updated to date: {date + hourminute}\nand output_bucket_path to {prefix}')

    return data['storage']['output_bucket'], prefix

def lambda_handler(event, context):
    """
    Handler function to kick off the NWM 2 NGEN forcingprocessor
    
    """
    # Start the EC2 instance
    instance_id = 'i-066cb631f20ae0eb5'
    client_ec2.start_instances(InstanceIds=[instance_id])   
    if not wait_for_instance_status(instance_id, 'Online'):
        raise Exception(f"EC2 instance {instance_id} did not reach 'Online' state")
        
    bucket, prefix = update_conf()

    command = 'source /home/ec2-user/venv/bin/activate && python /home/ec2-user/ngen-datastream/forcingprocessor/src/nwmforcing2ngen.py dailyrun' 
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
    output['bucket']      = bucket
    output['prefix']      = prefix
    return output
