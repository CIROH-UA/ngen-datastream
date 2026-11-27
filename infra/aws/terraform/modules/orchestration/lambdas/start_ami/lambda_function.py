import boto3
import botocore
import time, os, json

global client_ec2
client_ec2 = boto3.client("ec2", region_name=os.environ["AWS_REGION"])

# a second EC2 client with boto3's automatic retries turned off for spot requests
client_ec2_no_retry = boto3.client(
    "ec2",
    region_name=os.environ["AWS_REGION"],
    config=botocore.config.Config(retries={"total_max_attempts": 1}),
)

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
    client = boto3.client(
        "pricing", region_name="us-east-1"
    )  # Pricing is only available in us-east-1

    location = REGION_NAME_MAP.get(region)
    if not location:
        raise ValueError(
            f"Region {region} not mapped to a pricing API location string."
        )

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
        MaxResults=1,
    )

    if not response["PriceList"]:
        raise RuntimeError(
            f"No pricing data found for {instance_type} in {region} ({location})."
        )

    price_item = json.loads(response["PriceList"][0])
    terms = price_item["terms"]["OnDemand"]
    price_dimensions = next(
        iter(next(iter(terms.values()))["priceDimensions"].values())
    )
    price_per_hour = float(price_dimensions["pricePerUnit"]["USD"])

    return price_per_hour


# Error codes that mean "this instance type in this AZ is sold out right now" —
# worth retrying elsewhere. Anything else (throttles, auth, bad params) must
# bubble up so the state machine's backoff handles it instead of amplifying it.
CAPACITY_ERROR_CODES = {
    "InsufficientInstanceCapacity",
    "InsufficientCapacityOnHost",
    "InsufficientHostCapacity",
    "InsufficientReservedInstanceCapacity",
    "Unsupported",
    "SpotMaxPriceTooLow"
}

# Graviton instance families to try for spot in order of preference.
SPOT_FAMILIES = ["m8g", "m7g", "m6g", "r8g", "r7g"]


def get_spot_instance_types(instance_type):
    """
   returns the instance types to try for spot, same size, requested type first.

    Example: "m8g.2xlarge" -> ["m8g.2xlarge", "m7g.2xlarge", "m6g.2xlarge",
                               "r8g.2xlarge", "r7g.2xlarge"]
    handles instances outside SPOT_FAMILIES: "t4g.small" -> ["t4g.small"]
    """
    family, size = instance_type.split(".", 1)
    if family not in SPOT_FAMILIES:
        return [instance_type]

    instance_types = [instance_type]
    for other_family in SPOT_FAMILIES:
        if other_family != family:
            instance_types.append(other_family + "." + size)
    return instance_types


def get_default_subnets():
    try:
        resp = client_ec2.describe_subnets(
            Filters=[{"Name": "default-for-az", "Values": ["true"]}]
        )
        return [
            s["SubnetId"]
            for s in sorted(resp["Subnets"], key=lambda s: s["AvailabilityZone"])
        ]
    except Exception as e:
        print(f"Could not list default subnets, AZ fallback disabled: {e}")
        return []


def launch_with_capacity_fallbacks(params, original_error):
    """Retry the launch across per-AZ default subnets until one has capacity.

    The normal launch omits SubnetId, letting EC2 pick an AZ — which fails as a
    unit when that AZ is out of capacity. Capacity errors are AZ-specific, so
    walking the other AZs usually resolves in seconds, versus a full
    state-machine retry that re-asks the same sold-out AZ.
    """
    subnets = get_default_subnets()
    if not subnets:
        raise Exception(
            f"AZ fallback unavailable (default subnet lookup failed or returned none). Original capacity error: {original_error}"
        )
    for subnet in subnets:
        attempt = dict(params)
        attempt["SubnetId"] = subnet
        try:
            print(f"capacity fallback attempt in {subnet}")
            return client_ec2.run_instances(**attempt)
        except botocore.exceptions.ClientError as e:
            code = e.response["Error"]["Code"]
            if code not in CAPACITY_ERROR_CODES:
                raise
            print(f"no capacity in {subnet}: {code}")
    raise Exception(
        f"No capacity in any of {len(subnets)} availability zones tried. Original error: {original_error}"
    )


def launch_spot_in_other_azs_and_families(params):
    """
    tries spot for every instance type from get_spot_instance_types() in every AZ.

    Order: m8g in AZ a, b, c, ... then m7g in AZ a, b, c, ... and so on.
    Returns the run_instances response for the first launch that works, or None if
    nothing had spot capacity. On None, the caller falls back to on-demand (same as before).

    Replaces the old spot fallback, which only tried other AZs for the same instance type.
    """
    subnets = get_default_subnets()
    instance_types = get_spot_instance_types(params["InstanceType"])

    for instance_type in instance_types:
        for subnet in subnets:
            attempt = dict(params)
            attempt["InstanceType"] = instance_type
            attempt["SubnetId"] = subnet

            print(f"Trying spot: {instance_type} in {subnet}")
            try:
                return client_ec2_no_retry.run_instances(**attempt)
            except botocore.exceptions.ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code in CAPACITY_ERROR_CODES:
                    print(f"No spot instances available: {error_code}, trying the next one")
                    continue

                print(f"  stopping spot search: {error_code}")
                return None

    print("No spot capacity for any instance type in any AZ")
    return None


def wait_for_instance_running(instance_id, timeout=300):
    start = time.time()
    retries = 0
    while time.time() - start < timeout:
        try:
            response = client_ec2.describe_instances(InstanceIds=[instance_id])
            state = response["Reservations"][0]["Instances"][0]["State"]["Name"]
            if state == "running":
                return True
            print(f"Instance {instance_id} is in state: {state}")
            retries += 1
        except Exception as e:
            print(f"Error checking instance state: {e}")
        time.sleep(min(30, 2 ** int(0.5 * retries)))  # cap backoff
    return False


def lambda_handler(event, context):

    t0 = time.time()
    event["t0"] = t0
    event["ii_s3_object_checked"] = False
    if not "timeout_s" in event["run_options"]:
        print(f"Setting timeout_s to default 3600 seconds")
        event["run_options"]["timeout_s"] = 3600

    if not "retry_attempt" in event:
        event["retry_attempt"] = 0
    else:
        event["retry_attempt"] += 1

    event["region"] = os.environ["AWS_REGION"]

    if event["run_options"].get("ii_cheapo", None):
        if event["retry_attempt"] == 0:
            print(
                "First attempt, using spot instance with price cap at on-demand price"
            )
            on_demand_price = get_ondemand_price(
                event["instance_parameters"]["InstanceType"], event["region"]
            )
            event["instance_parameters"]["InstanceMarketOptions"] = {
                "MarketType": "spot",
                "SpotOptions": {
                    "MaxPrice": f"{on_demand_price:.4f}",
                    "SpotInstanceType": "one-time",
                    "InstanceInterruptionBehavior": "terminate",
                },
            }
        elif event["retry_attempt"] == event["run_options"]["n_retries_allowed"]:
            print("Last retry attempt, using on-demand instance")
            event["instance_parameters"].pop("InstanceMarketOptions", None)
        else:
            print(
                f"Retrying spot instance, attempt {event['retry_attempt']} of {event['run_options']['n_retries_allowed']}"
            )

    event["instance_parameters"]["MaxCount"] = 1
    event["instance_parameters"]["MinCount"] = 1
    params = event["instance_parameters"]

    # a spot request uses the no-retry client with a single attempt
    if params.get("InstanceMarketOptions"):
        first_client = client_ec2_no_retry
    else:
        first_client = client_ec2

    try:
        response = first_client.run_instances(**params)
    except botocore.exceptions.ClientError as e:
        error_msg = e.response["Error"]["Message"]
        error_code = e.response["Error"]["Code"]
        print(f"run_instances failed: {error_code}: {error_msg}")

        if params.get("InstanceMarketOptions", None):
            response = None
            # Try launching spot instances in other AZs before falling back to on-demand
            if error_code in CAPACITY_ERROR_CODES:
                print(
                    "No spot capacity in default AZ, trying spot in other AZs and instance families"
                )
                try:
                    response = launch_spot_in_other_azs_and_families(params)
                except Exception as e_spot:
                    print(f"Spot AZ fallback failed: {e_spot}")
            if response is None:
                print(
                    "Spot instance request failed, falling back to on-demand instance"
                )
                params.pop("InstanceMarketOptions", None)
                try:
                    response = client_ec2.run_instances(**params)
                except botocore.exceptions.ClientError as e2:
                    error_code = e2.response["Error"]["Code"]
                    if error_code not in CAPACITY_ERROR_CODES:
                        raise
                    response = launch_with_capacity_fallbacks(
                        params, e2.response["Error"]["Message"]
                    )
        elif error_code in CAPACITY_ERROR_CODES:
            response = launch_with_capacity_fallbacks(params, error_msg)
        else:
            raise Exception(
                f"Instance request failed, no fallback available. Error: {error_msg}"
            )
    except Exception as e:
        # Catch any other unexpected errors
        print(f"Unexpected error: {e}")
        raise

    launched = response["Instances"][0]
    instance_id = launched["InstanceId"]
    print(
        f"Launched {instance_id} type={launched['InstanceType']} az={launched['Placement']['AvailabilityZone']}"
    )

    if not instance_id is None:
        if not wait_for_instance_running(instance_id):
            raise Exception(f"EC2 instance {instance_id} did not reach 'Online' state")
        print(f"{instance_id} has been launched and running")

    event["instance_parameters"]["InstanceId"] = instance_id

    return event


if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser()
    parser.add_argument("--exec", type=str, help="")
    args = parser.parse_args()
    with open(args.exec, "r") as fp:
        exec = json.load(fp)
    lambda_handler(exec, "")
