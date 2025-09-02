import boto3
import time

client_ec2 = boto3.client('ec2')

def confirm_detach(volume_id):
    while True:
        response = client_ec2.describe_volumes(
            Filters=[
            {
                'Name': 'volume-id',
                'Values': [volume_id],
            },
        ],)
        if response['Volumes'][0]['State'] != "available":
            print(f'Volume not yet available')
            time.sleep(1)
        else:
            return
        
def confirm_instance_termination(instance_id):
    while True:
        response = client_ec2.describe_instances(
            InstanceIds=[
                instance_id
            ]
        )
        if response['Reservations'][0]['Instances'][0]['State']['Name'] != 'terminated':
            print(f'Instance not yet terminated')
            time.sleep(1)
        else:
            print(f'Instance {instance_id} terminated')
            return        

def lambda_handler(event, context):
    """
    Generic Poller funcion    
    """

    instance_id = event['instance_parameters']['InstanceId']
    if instance_id is None:
        print('No InstanceId found in event, exiting')
        return event
    response = client_ec2.describe_volumes(
        Filters=[
        {
            'Name': 'volume-id',
            'Values': [event['volume_id']],
        },
    ],)
    print(response)
    volume_id=event['volume_id']
    if event["run_options"]["ii_terminate_instance"]:
        response = client_ec2.terminate_instances(
            InstanceIds=[
                instance_id,
            ],
        )
        confirm_instance_termination(instance_id)
    else:
        if event["run_options"]["ii_delete_volume"]:
            print(f'Instance VolumeId {volume_id} located.')
            response = client_ec2.detach_volume(
                InstanceId=instance_id,
                VolumeId=volume_id,
                DryRun=False
            )
            confirm_detach(volume_id)
            print(f'EBS volume {instance_id} has been successfully detached.')
            response = client_ec2.delete_volume(
                VolumeId=volume_id,
                DryRun=False
            )   
            print(f'EBS volume {volume_id} has been successfully deleted.')     
        else:
            print(f"Volume {volume_id} remains attached or available and is still incurring costs.")

    if "failedInput" in event or (event['run_options'].get('ii_check_s3',False) and not event['run_options'].get('ii_s3_object_checked', False)):
        if event['retry_attempt'] == event['run_options']['n_retries_allowed']:
            pass
        else:
            if "InstanceId" in event['instance_parameters']: del event['instance_parameters']['InstanceId']
            if "volume_id" in event: del event['volume_id']
            if "command_id" in event: del event['command_id']        
            if "failedInput" in event: del event['failedInput']

    return event