import boto3
import botocore
from botocore.config import Config
import time, os, json

# Configure retry for EC2 API throttling (RequestLimitExceeded)
# https://boto3.amazonaws.com/v1/documentation/api/latest/guide/retries.html
retry_config = Config(
    retries={
        'total_max_attempts': 15,
        'mode': 'standard'
    }
)

global client_ec2
client_ec2 = boto3.client('ec2', region_name=os.environ['AWS_REGION'], config=retry_config)

REGION_NAME_MAP = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)",
    "us-west-2": "US West (Oregon)",
    "eu-west-1": "EU (Ireland)",
    "eu-west-2": "EU (London)",
    "eu-central-1": "EU (Frankfurt)",
}

def get_ondemand_price(instance_type: str, region: str, os: str = "Linux") -> float:
    """
    Query AWS Pricing API to get the On-Demand hourly price for an EC2 instance.

    Args:
        instance_type (str): EC2 instance type (e.g., "t3.micro").
        region (str): AWS region code (e.g., "us-east-1").
        os (str): Operating system ("Linux", "Windows", etc.)

    Returns:
        float: On-Demand hourly price in USD.
    """
    client = boto3.client("pricing", region_name="us-east-1")  # Pricing is only available in us-east-1

    location = REGION_NAME_MAP.get(region)
    if not location:
        raise ValueError(f"Region {region} not mapped to a pricing API location string.")

    response = client.get_products(
        ServiceCode="AmazonEC2",
        Filters=[
            {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": os},
            {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
            {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
            {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
        ],
        MaxResults=1
    )

    if not response["PriceList"]:
        raise RuntimeError(f"No pricing data found for {instance_type} in {region} ({location}).")

    price_item = json.loads(response["PriceList"][0])
    terms = price_item["terms"]["OnDemand"]
    price_dimensions = next(iter(next(iter(terms.values()))["priceDimensions"].values()))
    price_per_hour = float(price_dimensions["pricePerUnit"]["USD"])

    return price_per_hour

def wait_for_instance_running(instance_id, timeout=300):
    start = time.time()
    retries = 0
    while time.time() - start < timeout:
        try:
            response = client_ec2.describe_instances(InstanceIds=[instance_id])
            state = response['Reservations'][0]['Instances'][0]['State']['Name']
            if state == "running":
                return True
            print(f"Instance {instance_id} is in state: {state}")
            retries += 1
        except Exception as e:
            print(f"Error checking instance state: {e}")
        time.sleep(min(30, 2 ** int(0.5*retries)))  # cap backoff
    return False

    
def lambda_handler(event, context):

    t0 = time.time()
    event['t0'] = t0
    event['ii_s3_object_checked'] = False
    if not "timeout_s" in event['run_options']:
        print(f'Setting timeout_s to default 3600 seconds')
        event['run_options']['timeout_s'] = 3600

    if not "retry_attempt" in event:
        event['retry_attempt'] = 0
    else:
        event['retry_attempt'] += 1

    event['region'] = os.environ['AWS_REGION']

    if event['run_options'].get('ii_cheapo', None):
        if event['retry_attempt'] == 0:
            print('First attempt, using spot instance with price cap at on-demand price')
            on_demand_price = get_ondemand_price(event['instance_parameters']['InstanceType'], event['region'])
            event['instance_parameters']['InstanceMarketOptions'] = {
                'MarketType': 'spot',
                'SpotOptions': {
                    'MaxPrice': f'{on_demand_price:.4f}',
                    "SpotInstanceType": "one-time",
                    "InstanceInterruptionBehavior": "terminate"
                }
            }
        elif event['retry_attempt'] == event['run_options']['n_retries_allowed']:
            print('Last retry attempt, using on-demand instance')
            event['instance_parameters'].pop('InstanceMarketOptions', None)
        else:
            print(f'Retrying spot instance, attempt {event["retry_attempt"]} of {event["run_options"]["n_retries_allowed"]}')

    event['instance_parameters']['MaxCount'] = 1
    event['instance_parameters']['MinCount'] = 1

    # Remove InstanceId if present (can happen on retries after a previous successful run)
    # run_instances() does not accept InstanceId as a parameter - it's only for tracking
    params = event['instance_parameters'].copy()
    params.pop('InstanceId', None)

    try:
        response = client_ec2.run_instances(**params)
        instance_id = response['Instances'][0]['InstanceId']
    except botocore.exceptions.ClientError as e:
        error_msg = e.response['Error']['Message']
        print(f"run_instances failed: {error_msg}")
        
        if event['instance_parameters'].get('InstanceMarketOptions', None):
            print("Spot instance request failed, falling back to on-demand instance")
            event['instance_parameters'].pop('InstanceMarketOptions', None)
            response = client_ec2.run_instances(**event['instance_parameters'])
            instance_id = response['Instances'][0]['InstanceId']
        else:
            raise Exception(f"Instance request failed, no fallback available. Error: {error_msg}")
    except Exception as e:
        # Catch any other unexpected errors
        print(f"Unexpected error: {e}")
        raise

    if not instance_id is None:
        if not wait_for_instance_running(instance_id):
            raise Exception(f"EC2 instance {instance_id} did not reach 'Online' state")
        print(f'{instance_id} has been launched and running')

    event['instance_parameters']['InstanceId']  = instance_id

    return event

if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument("--exec", type=str, help="")
    args      = parser.parse_args()
    with open(args.exec,'r') as fp:
        exec = json.load(fp)
    lambda_handler(exec,"")