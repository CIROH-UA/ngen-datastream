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
    client_ssm = boto3.client('ssm',event['region'])
    client_ec2 = boto3.client('ec2',event['region'])

    instance_id = event['instance_parameters']['InstanceId']

    if "datastream_command_options" in event:
        ds_options = event["datastream_command_options"]
        event['commands'] = []
        if "s3_bucket" in ds_options:
            bucket = ds_options["s3_bucket"]
            prefix = ds_options["object_prefix"]
            event['commands'].append("runuser -l ec2-user -c 'mkdir -p /home/ec2-user/ngen-datastream/data/mount'")
            event['commands'].append(f"runuser -l ec2-user -c 'mount-s3 {bucket} /home/ec2-user/ngen-datastream/data/mount'")
        nprocs = ds_options["nprocs"]
        start = ds_options["start_time"]
        end = ds_options["end_time"]
        forcing_source = ds_options["forcing_source"]
        hf_version = ds_options["hydrofabric_version"]
        subset_id = ds_options["subset_id"]
        subset_type = ds_options["subset_id_type"]
        event['commands'].append(f"runuser -l ec2-user -c 'hfsubset -w medium_range -s nextgen -v {hf_version} -l divides,flowlines,network,nexus,forcing-weights,flowpath-attributes,model-attributes -o datastream.gpkg -t {subset_type} {subset_id}'")
        command_str = f"runuser -l ec2-user -c 'cd /home/ec2-user/ngen-datastream && ./scripts/stream.sh -s {start} -e {end} -C {forcing_source} -d $(pwd)/data/datastream -g $(pwd)/datastream.gpkg -R $(pwd)/configs/ngen/realization_sloth_nom_cfe_pet_troute.json -n {nprocs}'"
        if "s3_bucket" in ds_options: 
            command_str += f" -S $(pwd)/data/mount -o {prefix}"
        event['commands'].append(command_str)    

    try:
        response = client_ec2.describe_instances(
           InstanceIds=[
               instance_id
           ]
        )
        print(response)
        if response['Reservations'][0]['Instances'][0]['State']['Name'] == "running":
            print(f'Instance is running, executing command')
            print(f'{instance_id}')
            print(event)
            response = client_ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName='AWS-RunShellScript',
                Parameters={'commands': event['commands'],
                            "executionTimeout": [f"{3600*24}"]
                            }
            )
        else:
            print(response)
    except client_ssm.exceptions.InvalidInstanceId as e:
        print(e.response)
    wait_for_command_response(response,instance_id)
    print(f'{instance_id} is launched')

    event['command_id']  = response['Command']['CommandId']

    date = datetime.now()
    date_fmt = date.strftime('%Y%m%d')    
    if 'DATE' in event['obj_key']:
        key_str = event['obj_key']        
        event['obj_key'] = key_str.replace('DATE',date_fmt)        

    return event
