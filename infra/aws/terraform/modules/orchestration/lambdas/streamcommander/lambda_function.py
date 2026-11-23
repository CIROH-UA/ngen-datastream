import boto3
import time
import json

# Vendored into the lambda zip from infra/common/python (see lambda.tf).
from research_datastream_core import (
    extract_s3_bucket,
    extract_s3_prefix,
)


def wait_for_command_response(response, instance_id):
    iters = 0
    max_iters = 10
    while True:
        try:
            command_id = response["Command"]["CommandId"]
            print(command_id)
            output = client_ssm.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
            print(f"Response obtained -> {output}")
            break
        except:
            print(f"waiting for command response...")
            time.sleep(1)
            iters += 1
            if iters > max_iters:
                print(f"FAILED")
                break


def lambda_handler(event, context):
    """
    Handler function to issue commands to an ec2

    """
    global client_ssm, client_ec2
    client_ec2 = boto3.client("ec2", region_name=event["region"])

    instance_id = event["instance_parameters"]["InstanceId"]

    if "datastream_command_options" in event:
        ds_options = event["datastream_command_options"]
        event["commands"] = []
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
        command_str += "'"
        event["commands"].append(command_str)
        event.pop("datastream_command_options")

    # DAILY was resolved by the input gate before launch.
    bucket = extract_s3_bucket(event["commands"])
    prefix = extract_s3_prefix(event["commands"])

    if not prefix is None and not bucket is None:
        client_s3 = boto3.client("s3", region_name=event["region"])
        key = f"{prefix}/datastream-metadata/execution.json"
        if "forcing" in prefix:
            key = f"{prefix}/metadata/execution.json"
        client_s3.put_object(Body=json.dumps(event, indent=4), Bucket=bucket, Key=key)

    ii_check_role = True
    max_wait = 120
    start_time = time.time()
    while ii_check_role:
        if time.time() - start_time > max_wait:
            raise TimeoutError(
                "Timed out waiting for instance to be running with correct IAM role"
            )
        time.sleep(1)
        response = client_ec2.describe_instances(InstanceIds=[instance_id])
        event["volume_id"] = response["Reservations"][0]["Instances"][0][
            "BlockDeviceMappings"
        ][0]["Ebs"]["VolumeId"]
        print(response)
        if response["Reservations"][0]["Instances"][0]["State"]["Name"] == "running":
            print(f"Instance is running, checking IAM role")
            iam_instance_profile = (
                response["Reservations"][0]["Instances"][0]
                .get("IamInstanceProfile")["Arn"]
                .split("/")[-1]
            )
            print(f"Instance is running with role {iam_instance_profile}")
            assert (
                iam_instance_profile
                == event["instance_parameters"]["IamInstanceProfile"]["Name"]
            )
            ii_check_role = False
            print(f"IAM confirmed, issuing command")

    client_ssm = boto3.client("ssm")
    print(f"Client established, sending command")
    ii_send_command = True
    max_wait = 300
    start_time = time.time()
    while ii_send_command:
        if time.time() - start_time > max_wait:
            raise TimeoutError("Timed out waiting to send command to instance")
        try:
            time.sleep(1)
            response = client_ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={
                    "commands": event["commands"],
                    "executionTimeout": [f"{3600 * 24}"],
                },
            )
            ii_send_command = False
        except client_ssm.exceptions.ClientError as e:
            print(str(e))

    wait_for_command_response(response, instance_id)
    print(f"Commands have been issued")

    event["command_id"] = response["Command"]["CommandId"]

    return event


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--exec", type=str, help="")
    args = parser.parse_args()
    with open(args.exec, "r") as fp:
        exec = json.load(fp)
        exec["region"] = "us-east-1"
        exec["instance_parameters"]["InstanceId"] = ""
    lambda_handler(exec, "")
