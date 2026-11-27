import boto3
import time
import datetime
from datetime import timezone
import json

# Vendored into the lambda zip from infra/common/python (see lambda.tf).
from research_datastream_core import output_marker

client_s3 = boto3.client("s3")


def wait_for_object_existence(bucket_name, prefix):

    count = 0
    while count < 10:
        response = client_s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        if "Contents" in response:
            print(f"Objects exists in bucket {bucket_name} at prefix {prefix}")
            return True
        else:
            count += 1
            time.sleep(1)
    return False


def lambda_handler(event, context):

    if event["run_options"]["ii_check_s3"]:
        marker = output_marker(event["commands"])
        if marker is None:
            raise Exception(
                f"User specified ii_check_s3, but no s3_bucket or s3_prefix were not found in commands"
            )
        bucket, prefix = marker
        print(f"Checking if any objects with prefix {prefix} exists in {bucket}")
        if not wait_for_object_existence(bucket, prefix):
            store_failed_execution(event, bucket)
        else:
            event["ii_s3_object_checked"] = True
            print(
                f"Found s3 object with prefix {prefix} in {bucket}, proceeding with execution."
            )

    else:
        print(f"No s3 object check was performed.")

    return event


def store_failed_execution(execution, bucket):
    print(f"Execution failed, storing execution in {bucket}")
    timestamp = datetime.datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    key = f"test/cicd/nrds/failed_executions/{timestamp}.json"
    client_s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(execution))
    print(f"Execution stored in {bucket} at {key}")


if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execution", dest="execution", type=str, help="", default=None
    )
    args = parser.parse_args()

    with open(args.execution, "r") as fp:
        execution = json.load(fp)

    lambda_handler(execution, "")
