import boto3
import json
import time
import datetime

client_s3  = boto3.client('s3')
client_ssm = boto3.client('ssm')

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
            
def update_conf(bucket, run_type):

    conf_path = '/tmp/conf.json'
    client_s3.download_file(bucket, f'{run_type}_template_conf.json', conf_path)
    with open(conf_path,'r') as fp:
        data = json.load(fp)
        
    date = datetime.datetime.now()
    date = date.strftime('%Y%m%d')

    hourminute = '0000'
    
    data['forcing']['start_date'] = date + hourminute
    data['forcing']['end_date']   = date + hourminute
    
    prefix = f"{run_type}/{date}"
    data['storage']['output_bucket_path'] = prefix
    
    conf_run = f'{run_type}.json'
    with open('/tmp/' + conf_run,'w') as fp:
        json.dump(data,fp)
    client_s3.upload_file('/tmp/' + conf_run, bucket, conf_run)
    
    print(f'The {run_type} config has been updated to date: {date + hourminute}\nand output_bucket_path to {prefix}')

    return data['storage']['output_bucket'], prefix

def lambda_handler(event, context):
    """
    Handler function to kick off the NWM 2 NGEN forcingprocessor
    
    """

    instance_id = event['instance_id']
    run_type    = event['run_type']
    bucket      = event['config_bucket']

    output_bucket, prefix = update_conf(
        bucket,
        run_type
        )

    command = f'source /home/ec2-user/venv/bin/activate && python /home/ec2-user/ngen-datastream/forcingprocessor/src/nwmforcing2ngen.py {run_type}' 
    response = client_ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': [command]}
    )
    wait_for_command_response(response,instance_id)
    print(f'{instance_id} is launched and processing forcings')

    event['command_id']  = response['Command']['CommandId']
    event['bucket']      = output_bucket
    event['prefix']      = prefix

    return event
