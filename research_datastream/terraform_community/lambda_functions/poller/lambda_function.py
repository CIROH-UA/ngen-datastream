import boto3
import time

def get_command_result(command_id,instance_id):
    
    try:
        output = client_ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id,
            )
        if output['Status'] in ['Success', 'Failed', 'Canceled']:
            print(f'Command has completed -> {output}')
    except:
        output = None

    return output

def lambda_handler(event, context):
    """
    Generic Poller funcion    
    """
    t0 = time.perf_counter()
    timeout_s = event['run_options']['timeout_s']

    global client_ssm, client_ec2
    client_ssm = boto3.client('ssm',region_name=event['region'])
    client_ec2 = boto3.client('ec2',region_name=event['region'])    

    command_id  = event['command_id']
    instance_id = event['instance_parameters']['InstanceId']
    output = get_command_result(command_id,instance_id)

    ii_pass = False
    ii_time = False
    while not ii_pass and not ii_time:
        output = get_command_result(command_id,instance_id)
        if output['Status'] == 'Success':
            print(f'Command has succeeded!')
            ii_pass = True
            break
        elif output['Status'] == 'InProgress':
            ii_pass = False   
            print(f'Commands are still in progress. Waiting 5 seconds and checking again')
            if (time.perf_counter() - t0) > 800: 
                print(f'Cycling...')
                ii_time = True
            duration = time.time() - event['t0']
            if duration >= timeout_s:
                print(f'Duration -> {duration}\nTimeout -> {timeout_s}')
                raise Exception(f'Commands duration have exceed the timeout specified in the execution')
            time.sleep(5) 
        elif output['Status'] in ["Pending", "Delayed"]:
            time.sleep(5)
            continue
        else:
            raise Exception(f'Command failed {output}')         
    
    event['ii_pass'] = ii_pass
    return event
    
