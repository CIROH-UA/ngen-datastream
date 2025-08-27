import boto3
import time
import re
import json
from datetime import datetime, timezone, timedelta

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
    today = datetime.now(timezone.utc)

    instance_id = event['instance_parameters']['InstanceId']

    if event.get("retry_attempt",0) == 0:
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
            command_str = f"runuser -l ec2-user -c 'cd /home/ec2-user/datastream && ./scripts/datastream -s {start} -e {end} -C {forcing_source} -I {subset_id} -i {subset_type} -v {hf_version} -d $(pwd)/data/datastream -R {realization} -n {nprocs}"
            if "s3_bucket" in ds_options: 
                command_str += f" -S {bucket} -o {prefix}"
            command_str += '\''
            event['commands'].append(command_str) 
            event.pop("datastream_command_options")  

        forcing_file = None
        for jcmd in event["commands"]:
            bucket_pattern = r"(?i)--s3_bucket[=\s']+([^\s']+)"
            match = re.search(bucket_pattern, jcmd)
            if match: 
                bucket = match.group(1)
            prefix_pattern = r"(?i)--s3_prefix[=\s']+([^\s']+)"
            match = re.search(prefix_pattern, jcmd)
            if match: 
                prefix = match.group(1)   
            forcing_source_pattern = r"(?i)--forcing_source[=\s']+([^\s']+)"
            match = re.search(forcing_source_pattern, jcmd)
            if match: 
                forcing_source = match.group(1)      

            forcing_file_pattern = r"(?i)-F[=\s']+([^\s']+)"
            match = re.search(forcing_file_pattern, jcmd)
            if match: 
                forcing_file = match.group(1) 

        if "DAILY" in prefix: 
            # Create s3 path with DAILY replaced
            prefix_daily = prefix
            fcst_cycle = 16 # for analysis assim extend
            if "SHORT_RANGE" in forcing_source:
                fcst_cycle = int(forcing_source[-2:])
            elif "MEDIUM_RANGE" in forcing_source:
                fcst_cycle = int(forcing_source[-4:-2])          
            if today.hour < fcst_cycle:
                today = (today - timedelta(days=1))
            today = today.strftime('%Y%m%d')        
            prefix = re.sub(r"\DAILY",today,prefix)   
            escaped_path = re.escape(prefix_daily)
            prefix_daily_pattern = escaped_path.replace('DAILY', r'(?P<date>DAILY)')

            for j,jcmd in enumerate(event["commands"]):
                match = re.search(prefix_daily_pattern, jcmd)
                replacement = prefix_daily.replace('DAILY', today)
                if match: 
                    new_str = re.sub(prefix_daily_pattern, replacement, jcmd)
                    event["commands"][j] = re.sub(prefix_daily_pattern, replacement, jcmd)

        if forcing_file is not None:
            # Shifting forcing file times based on ensemble member
            escaped = re.escape(forcing_file)

            # Make DAILY replaceable whether or not MEDIUM_RANGE is found
            escaped = escaped.replace('DAILY', r'(?P<date>DAILY)')

            shifted_forcing = forcing_file  # default, if no shift occurs

            if "MEDIUM_RANGE" in forcing_source:
                ensemble_member = int(forcing_source[-1]) 
                nhrs_shift = 6 * (ensemble_member - 1) 
                m = re.search(r'/(\d{2})/.*?t(\d{2})z', forcing_file)

                if m and nhrs_shift:
                    hh_folder = int(m.group(1)) 
                    shifted_raw = hh_folder - nhrs_shift
                    new_hour = shifted_raw % 24

                    if shifted_raw < 0:
                        ndays = (abs(shifted_raw) // 24) + 1
                        today = (datetime.strptime(today, '%Y%m%d') - timedelta(days=ndays)).strftime('%Y%m%d')

                    shifted_forcing = forcing_file
                    shifted_forcing = re.sub(r'/\d{2}/', f'/{new_hour:02d}/', shifted_forcing, count=1)
                    shifted_forcing = re.sub(r't\d{2}z', f't{new_hour:02d}z', shifted_forcing, count=1)

                    # Adjust regex pattern to allow shifted values
                    escaped = escaped.replace(re.escape(f'/{int(m.group(1)):02d}/'), r'/\d{2}/', 1)
                    escaped = escaped.replace(re.escape(f't{int(m.group(2)):02d}z'), r't\d{2}z', 1)

            # Compile regex for matching in command string
            forcing_pattern = re.compile(escaped)

            # Always replace DAILY with `today` in the final replacement string
            if type(today) != str:
                today = today.strftime('%Y%m%d')
            replacement = shifted_forcing.replace('DAILY', today)

            for j, jcmd in enumerate(event["commands"]):
                # Replace in -F argument (forcing file path)
                if "-F" in jcmd:
                    forcing_pattern = re.compile(re.escape(forcing_file).replace('DAILY', r'(?P<date>DAILY)'))
                    replacement = shifted_forcing.replace('DAILY', today)
                    jcmd = forcing_pattern.sub(replacement, jcmd, count=1)

                # Replace in --S3_PREFIX argument, but keep DAILY in it
                if "--S3_PREFIX" in jcmd:
                    if "DAILY" in prefix: 
                        prefix_pattern = re.compile(re.escape(prefix_daily).replace('DAILY', r'(?P<date>DAILY)'))
                        replacement = prefix_daily.replace('DAILY', today) 
                        jcmd = prefix_pattern.sub(prefix_daily, jcmd, count=1) 

                event["commands"][j] = jcmd

    if not prefix is None and not bucket is None:
        client_s3 = boto3.client('s3',region_name=event['region'])  
        key = f"{prefix}/datastream-metadata/execution.json"
        if "forcing" in prefix:
            key = f"{prefix}/metadata/execution.json"
        client_s3.put_object(
            Body=json.dumps(event, indent=4),
            Bucket=bucket,
            Key=key
        )

    ii_check_role = True
    max_wait = 120
    start_time = time.time()
    while ii_check_role:
        if time.time() - start_time > max_wait:
            raise TimeoutError("Timed out waiting for instance to be running with correct IAM role")
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

    client_ssm = boto3.client('ssm')
    print(f'Client established, sending command')
    ii_send_command = True
    max_wait = 120
    start_time = time.time()
    while ii_send_command:
        if time.time() - start_time > max_wait:
            raise TimeoutError("Timed out waiting to send command to instance")
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
    print(f'Commands have been issued')

    event['command_id']  = response['Command']['CommandId']   

    return event

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--exec", type=str, help="")
    args      = parser.parse_args()
    with open(args.exec,'r') as fp:
        exec = json.load(fp)
        exec['region'] = "us-east-1"
        exec['instance_parameters']['InstanceId'] = ""
    lambda_handler(exec,"")

