import boto3

client_ec2 = boto3.client('ec2')

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
            'InstanceId': instance_id,
        },
    ],)

    volume_id=response['Volumes']['Attachments']['VolumeId']
    if event["run_options"]["ii_detach_volume"]:
        print(f'Instance VolumeId {volume_id} located.')
        response = client_ec2.detach_volume(
            InstanceId=instance_id,
            VolumeId=volume_id,
            DryRun=False
        )
        print(f'EBS volume {instance_id} has been successfully stopped.')
    else:
        print(f"Volume {volume_id} remains attached to the instance.")

