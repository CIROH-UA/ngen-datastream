import boto3
import time

client_ec2 = boto3.client("ec2")

# Defaults used to space out retries when the upstream NWM forcings are not
# yet available (see https://github.com/CIROH-UA/ngen-datastream/issues/391).
# Retry N waits min(base * backoff_rate**N, max) seconds before the next
# EC2StarterFromAMI attempt, instead of retrying immediately.
DEFAULT_RETRY_BACKOFF_BASE_S = 1800  # 30 minutes
DEFAULT_RETRY_BACKOFF_MAX_S = 7200  # 2 hours
DEFAULT_RETRY_BACKOFF_RATE = 2


def compute_backoff_seconds(retry_attempt, run_options):
    """
    Exponential backoff for state machine retries triggered by a failed
    s3 object check (e.g. delayed upstream NWM forcings). retry_attempt is
    0-indexed, so the wait before the *next* attempt uses retry_attempt + 1.
    """
    base = run_options.get("retry_backoff_base_s", DEFAULT_RETRY_BACKOFF_BASE_S)
    max_wait = run_options.get("retry_backoff_max_s", DEFAULT_RETRY_BACKOFF_MAX_S)
    rate = run_options.get("retry_backoff_rate", DEFAULT_RETRY_BACKOFF_RATE)
    wait_seconds = base * (rate ** (retry_attempt + 1))
    return int(min(wait_seconds, max_wait))


def confirm_detach(volume_id):
    while True:
        response = client_ec2.describe_volumes(
            Filters=[
                {
                    "Name": "volume-id",
                    "Values": [volume_id],
                },
            ],
        )
        if response["Volumes"][0]["State"] != "available":
            print(f"Volume not yet available")
            time.sleep(1)
        else:
            return


def confirm_instance_termination(instance_id):
    while True:
        response = client_ec2.describe_instances(InstanceIds=[instance_id])
        if response["Reservations"][0]["Instances"][0]["State"]["Name"] != "terminated":
            print(f"Instance not yet terminated")
            time.sleep(1)
        else:
            print(f"Instance {instance_id} terminated")
            return


def lambda_handler(event, context):
    """
    Generic Poller funcion
    """

    instance_id = event["instance_parameters"]["InstanceId"]
    if instance_id is None:
        print("No InstanceId found in event, exiting")
        return event
    response = client_ec2.describe_volumes(
        Filters=[
            {
                "Name": "volume-id",
                "Values": [event["volume_id"]],
            },
        ],
    )
    print(response)
    volume_id = event["volume_id"]
    if event["run_options"]["ii_terminate_instance"]:
        response = client_ec2.terminate_instances(
            InstanceIds=[
                instance_id,
            ],
        )
        confirm_instance_termination(instance_id)
    else:
        if event["run_options"]["ii_delete_volume"]:
            print(f"Instance VolumeId {volume_id} located.")
            response = client_ec2.detach_volume(
                InstanceId=instance_id, VolumeId=volume_id, DryRun=False
            )
            confirm_detach(volume_id)
            print(f"EBS volume {instance_id} has been successfully detached.")
            response = client_ec2.delete_volume(VolumeId=volume_id, DryRun=False)
            print(f"EBS volume {volume_id} has been successfully deleted.")
        else:
            print(
                f"Volume {volume_id} remains attached or available and is still incurring costs."
            )

    # wait_seconds defaults to 0 so the "Wait" state added to the state
    # machine is a no-op unless we're actually about to retry.
    event["wait_seconds"] = 0

    if "failedInput" in event or (
        event["run_options"].get("ii_check_s3", False)
        and not event["run_options"].get("ii_s3_object_checked", False)
    ):
        if event["retry_attempt"] == event["run_options"]["n_retries_allowed"]:
            pass
        else:
            if "InstanceId" in event["instance_parameters"]:
                del event["instance_parameters"]["InstanceId"]
            if "volume_id" in event:
                del event["volume_id"]
            if "command_id" in event:
                del event["command_id"]
            if "failedInput" in event:
                del event["failedInput"]

            event["wait_seconds"] = compute_backoff_seconds(
                event["retry_attempt"], event["run_options"]
            )
            print(
                f"Retry {event['retry_attempt'] + 1} of "
                f"{event['run_options']['n_retries_allowed']}: waiting "
                f"{event['wait_seconds']}s before next attempt to allow "
                f"delayed upstream forcings to become available."
            )

    return event
