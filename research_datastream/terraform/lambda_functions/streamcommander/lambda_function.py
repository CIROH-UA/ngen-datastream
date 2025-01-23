import boto3
import time
from datetime import datetime

def wait_for_command_response(response,instance_id):
    iters = 0
    max_iters = 10
    while True:
        try:
            command_id = response['Command']['CommandId']
            print(command_id)
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
    Handler function to issue commands to an ec2
    
    """
    global client_ssm, client_ec2    
    client_ec2 = boto3.client('ec2',region_name=event['region'])    

    instance_id = event['instance_parameters']['InstanceId']

    if "datastream_command_options" in event:
        ds_options = event["datastream_command_options"]
        event['commands'] = []
        if "s3_bucket" in ds_options:
            bucket = ds_options["s3_bucket"]
            prefix = ds_options["s3_prefix"]
        nprocs = ds_options["nprocs"]
        start = ds_options["start_time"]
        end = ds_options["end_time"]
        forcing_source = ds_options["forcing_source"]
        realization = ds_options["realization"]
        hf_version = ds_options["hydrofabric_version"]
        subset_id = ds_options["subset_id"]
        subset_type = ds_options["subset_id_type"]
        command_str = f"runuser -l ec2-user -c 'cd /home/ec2-user/ngen-datastream && ./scripts/ngen-datastream -s {start} -e {end} -C {forcing_source} -I {subset_id} -i {subset_type} -v {hf_version} -d $(pwd)/data/datastream -R {realization} -n {nprocs}"
        if "s3_bucket" in ds_options: 
            command_str += f" -S {bucket} -o {prefix}"
        command_str += '\''
        event['commands'].append(command_str)    

    ii_check_role = True
    while ii_check_role:
        try:
            time.sleep(1)
            response = client_ec2.describe_instances(
                InstanceIds=[
                    instance_id
                ]
            )
            event['volume_id'] = response['Reservations'][0]['Instances'][0]['BlockDeviceMappings'][0]['Ebs']['VolumeId']
            print(response)
            if response['Reservations'][0]['Instances'][0]['State']['Name'] == "running":
                print(f'Instance is running, checking IAM role')
                iam_instance_profile = response['Reservations'][0]['Instances'][0].get('IamInstanceProfile')['Arn'].split('/')[-1]
                print(f'Instance is running with role {iam_instance_profile}')
                assert iam_instance_profile == event['instance_parameters']['IamInstanceProfile']['Name']
                ii_check_role = False
                print(f'IAM confirmed, issuing command')
        except:
            print(f"Instance profile doesn't match! Trying again")

    client_ssm = boto3.client('ssm')
    print(f'Client established, sending command')
    ii_send_command = True
    while ii_send_command:
        try:
            time.sleep(1)
            response = client_ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName='AWS-RunShellScript',
                Parameters={'commands': event['commands'],
                            "executionTimeout": [f"{3600*24}"]
                            }
                )
            ii_send_command = False
        except client_ssm.exceptions.ClientError as e:
            print(str(e))

    wait_for_command_response(response,instance_id)
    print(f'{instance_id} is launched')

    event['command_id']  = response['Command']['CommandId']   

    return event
