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

def lambda_handler(event, context):
    """
    Generic Poller funcion    
    """

    instance_id = event['instance_parameters']['InstanceId']

    print(f'Shutting down processor {instance_id}')
    client_ec2.stop_instances(InstanceIds=[instance_id])

    waiter = client_ec2.get_waiter('instance_stopped')
    waiter.wait(InstanceIds=[instance_id])

    print(f'Instance {instance_id} has been successfully stopped.')
    response = client_ec2.describe_volumes(
        Filters=[
        {
            'Name': 'volume-id',
            'Values': [event['volume_id']],
        },
    ],)
    print(response)
    volume_id=event['volume_id']
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
        print(f'EBS volume {instance_id} has been successfully deleted.')     
    else:
        print(f"Volume {volume_id} remains attached or available and is still incurring costs.")

