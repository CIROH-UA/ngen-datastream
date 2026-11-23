import time

import boto3
from botocore.exceptions import ClientError

# Vendored into the lambda zip from infra/common/python (see lambda.tf).
from research_datastream_core import input_wait, required_inputs, substitute_daily


def exists(client_s3, uri):
    bucket, key = uri[len("s3://"):].split("/", 1)
    try:
        client_s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def lambda_handler(event, context):
    """
    Resolve DAILY once, then hold the launch until the run's forcing (-F) and
    restart (-t) files exist in S3.
    """
    now = time.time()
    run_options = event.get("run_options", {})

    # First call only: the MEDIUM_RANGE hour shift isn't idempotent, and later
    # calls must keep the date resolved when the schedule fired.
    if not event.get("ii_daily_resolved", False):
        if "commands" in event:
            event["commands"] = substitute_daily(
                event["commands"], retry_attempt=event.get("retry_attempt", 0)
            )
        event["ii_daily_resolved"] = True
        event["input_wait_started"] = now
        event["input_checks"] = 0

    inputs = []
    if run_options.get("ii_wait_for_inputs", True):
        inputs = required_inputs(event.get("commands", []))
    client_s3 = boto3.client("s3", region_name=event.get("region"))
    missing = [uri for uri in inputs if not exists(client_s3, uri)]

    wait_s, timed_out = input_wait(run_options, event["input_checks"], now - event["input_wait_started"])
    event["missing_inputs"] = missing
    event["ii_inputs_ready"] = not missing
    event["ii_inputs_timed_out"] = bool(missing) and timed_out
    event["input_wait_s"] = max(wait_s, 1)
    event["input_checks"] += 1

    if missing:
        print(
            f"Check {event['input_checks']}: missing {missing}; "
            + ("giving up" if event["ii_inputs_timed_out"] else f"next check in {event['input_wait_s']}s")
        )
    else:
        print(f"Check {event['input_checks']}: inputs present {inputs}")
    return event
