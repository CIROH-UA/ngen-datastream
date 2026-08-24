import boto3
import botocore.exceptions
import re
import time
from datetime import datetime, timezone
from typing import Optional

# Default poll interval between forcing-file existence checks in the state
# machine wait loop.
DEFAULT_FORCING_CHECK_WAIT_S = 60

# Maximum wall-clock time (seconds) to wait for the forcing file before the
# state machine gives up and fails.  Defaults to 24 hours.
DEFAULT_FORCING_CHECK_TIMEOUT_S = 86400


def resolve_forcing_s3_path(forcing_file: str) -> tuple[str, str]:
    """Parse an S3 URI of the form s3://bucket/key into (bucket, key).

    Raises ValueError if the URI is not a valid s3:// path.
    """
    if not forcing_file.startswith("s3://"):
        raise ValueError(
            f"Forcing file path does not look like an S3 URI: {forcing_file!r}"
        )
    without_scheme = forcing_file[len("s3://"):]
    bucket, _, key = without_scheme.partition("/")
    if not bucket or not key:
        raise ValueError(
            f"Could not parse bucket and key from S3 URI: {forcing_file!r}"
        )
    return bucket, key


def substitute_daily(path: str, today: str) -> str:
    """Replace the literal token DAILY with *today* (YYYYMMDD)."""
    return re.sub(r"(?<![A-Za-z0-9])DAILY(?![A-Za-z0-9])", today, path)


def s3_object_exists(bucket: str, key: str) -> bool:
    """Return True if the S3 object at bucket/key exists."""
    client_s3 = boto3.client("s3")
    try:
        client_s3.head_object(Bucket=bucket, Key=key)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def extract_forcing_file(commands: list) -> Optional[str]:
    """Return the first -F argument found in the command list, or None."""
    for cmd in commands:
        match = re.search(r"(?<!\w)-F[=\s']+([^\s']+)", cmd)
        if match:
            return match.group(1)
    return None


def lambda_handler(event, context):
    """Check that the forcing file specified via -F exists in S3.

    This lambda is called from the state machine *before* the EC2 instance is
    launched.  It parses the forcing file path from the datastream command,
    resolves any DAILY token to today's date, and then checks whether the
    corresponding S3 object is present.

    Return values added to the event:
      - ii_forcing_found (bool): True if the file exists (or no check needed).
      - forcing_check_start_time (float): epoch time of the first call;
        preserved on subsequent calls so the 24-hr timeout is measured from
        the very first attempt.
      - forcing_check_wait_s (int): seconds the state machine Wait state
        should sleep before invoking this lambda again when the file is absent.
    """
    run_options = event.get("run_options", {})

    # If forcing-file validation is disabled, skip the check entirely.
    if not run_options.get("ii_check_forcing", False):
        event["ii_forcing_found"] = True
        return event

    # Record the start time on the very first invocation so we can enforce the
    # 24-hr timeout across multiple state-machine loops.
    now = time.time()
    if "forcing_check_start_time" not in event:
        event["forcing_check_start_time"] = now

    timeout_s = run_options.get(
        "forcing_check_timeout_s", DEFAULT_FORCING_CHECK_TIMEOUT_S
    )
    elapsed = now - event["forcing_check_start_time"]
    if elapsed >= timeout_s:
        raise RuntimeError(
            f"Forcing file not available after {elapsed:.0f}s "
            f"(timeout={timeout_s}s). Giving up."
        )

    event["forcing_check_wait_s"] = run_options.get(
        "forcing_check_wait_s", DEFAULT_FORCING_CHECK_WAIT_S
    )

    # Locate the -F argument in the command list.
    commands = event.get("commands", [])
    forcing_file = extract_forcing_file(commands)

    if forcing_file is None:
        # No forcing file argument found; nothing to wait on.
        print("No -F argument found in commands; skipping forcing-file check.")
        event["ii_forcing_found"] = True
        return event

    # Replace the DAILY placeholder with today's UTC date.
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    resolved = substitute_daily(forcing_file, today)

    try:
        bucket, key = resolve_forcing_s3_path(resolved)
    except ValueError as exc:
        print(f"Forcing file is not an S3 path ({exc}); skipping existence check.")
        event["ii_forcing_found"] = True
        return event

    print(f"Checking for forcing file: s3://{bucket}/{key}")
    found = s3_object_exists(bucket, key)

    if found:
        print(f"Forcing file found: s3://{bucket}/{key}")
        event["ii_forcing_found"] = True
    else:
        remaining = timeout_s - elapsed
        print(
            f"Forcing file not yet available: s3://{bucket}/{key}. "
            f"Elapsed {elapsed:.0f}s / timeout {timeout_s}s "
            f"({remaining:.0f}s remaining). "
            f"Will retry in {event['forcing_check_wait_s']}s."
        )
        event["ii_forcing_found"] = False

    return event


if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser()
    parser.add_argument("--exec", type=str, help="Path to execution JSON")
    args = parser.parse_args()
    with open(args.exec, "r") as fp:
        exec_event = json.load(fp)
    result = lambda_handler(exec_event, "")
    print(json.dumps(result, indent=2))
