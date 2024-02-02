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
            
def get_conf(bucket_path,out_path):   
    conf_path = '/tmp/conf.json'
    client_s3.download_file(bucket_path, out_path, conf_path)
    with open(conf_path,'r') as fp:
        data = json.load(fp)   
    return data

def fix_time(data):
    date = datetime.datetime.now()
    date = date.strftime('%Y%m%d')

    hourminute = '0000'
    
    data['start_date'] = date + hourminute
    data['end_date']   = date + hourminute

    return data, date

def update_confs(bucket, run_type):

    conf_data     = get_conf(bucket,f'conf_{run_type}_template.json')
    conf_nwm_data = get_conf(bucket,f'conf_{run_type}_template_nwmfilenames.json')
        
    conf_data['forcing'], date = fix_time(conf_data['forcing'])
    conf_nwm_data, _           = fix_time(conf_nwm_data)
    
    prefix = f"{run_type}/{date}"
    conf_data['storage']['output_bucket_path'] = prefix
    
    conf_run = f'{run_type}.json'
    with open('/tmp/' + conf_run,'w') as fp:
        json.dump(conf_data,fp)
    client_s3.upload_file('/tmp/' + conf_run, bucket, conf_run)

    conf_run = f'{run_type}_nwmfilenames.json'
    with open('/tmp/' + conf_run,'w') as fp:
        json.dump(conf_nwm_data,fp)
    client_s3.upload_file('/tmp/' + conf_run, bucket, conf_run)
    
    print(f'The {run_type} config has been updated to date: {date}\nand output_bucket_path to {prefix}')

    return conf_data['storage']['output_bucket'], prefix  

def lambda_handler(event, context):
    """
    Handler function to kick off the NWM 2 NGEN forcingprocessor
    
    """

    instance_id = event['instance_parameters']['InstanceId']
    run_type    = event['run_type']
    bucket      = event['config_bucket']

    command = \
        f"source /home/ec2-user/venv-datastream/bin/activate && " + \
        f"python /home/ec2-user/ngen-datastream/forcingprocessor/src/nwm_filenames_generator.py https://{bucket}.s3.us-east-2.amazonaws.com/conf_{run_type}_template_nwmfilenames.json && " + \
        f"python /home/ec2-user/ngen-datastream/forcingprocessor/src/forcingprocessor.py https://{bucket}.s3.us-east-2.amazonaws.com/conf_{run_type}_template.json"

    output_bucket, prefix = update_confs(
        bucket,
        run_type
        )

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
