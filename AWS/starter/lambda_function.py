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

    # with open('./userdata.sh', 'r') as fp:
    #     userdata = fp.read()

    user_data = '''#!/bin/bash

# cli command to start instance
# aws ec2 run-instances --user-data file://user_data.txt --instance-type c5n.18xlarge --count 1 --image-id ami-08cba41c585e4a2e2 --region us-east-2 --key-name Processor --iam-instance-profile '{"Name":"Processor"}' --security-group-ids "sg-0fc864d44ef677a07" --profile jlaser_ciroh

echo "EXECUTING USER DATA"

cd /home/ec2-user

sudo dnf install git -y
python3 -m venv ./venv-datastream
git clone https://github.com/CIROH-UA/ngen-datastream.git
source ./venv-datastream/bin/activate && pip3 install --upgrade pip
pip3 install -r ./ngen-datastream/requirements.txt
deactivate

python3 -m venv ./venv-ngen-cal
git clone --branch realization_validation https://github.com/JordanLaserGit/ngen-cal.git
source ./venv-ngen-cal/bin/activate && pip3 install --upgrade pip
pip3 install -r ./ngen-cal/requirements.txt
pip3 install -e ./ngen-cal/python/ngen_conf
deactivate

# sudo dnf install go -y
# go install github.com/aaraney/ht@latest

touch /tmp/userdata_complete

echo "USERDATA COMPLETE"

        '''

    params             = event['instance_parameters']
    params['UserData'] = user_data

    response           = client_ec2.run_instances(**params)
    instance_id        = response['Instances'][0]['InstanceId']

    client_ec2.start_instances(InstanceIds=[instance_id])   
    if not wait_for_instance_status(instance_id, 'Online'):
        raise Exception(f"EC2 instance {instance_id} did not reach 'Online' state")
    print(f'{instance_id} has been launched and running')

    event['instance_parameters']['InstanceId']  = instance_id

    time.sleep(120)

    return event
