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

