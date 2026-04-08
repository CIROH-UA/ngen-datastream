import json
import re
import time
import boto3
from datetime import datetime, timezone, timedelta

sfn_client = boto3.client('stepfunctions')

# Delay retry to avoid competing with scheduled batches.
# Scheduled runs fire at the top of each hour (:00) and typically
# complete within 5-10 minutes. Waiting 10 minutes avoids overlap.
RETRY_DELAY_SECONDS = 600

# Max concurrent running executions before we consider the system busy
MAX_RUNNING_THRESHOLD = 30

# Additional wait if system is busy
BUSY_WAIT_SECONDS = 300

MAX_RETRIES = 2


def get_intended_date(execution_name, original_start_time):
    """
    Determine the intended processing date from the execution name and start time.

    Execution names follow: {model}_{forecast_type}_{vpu}_init{HH}_{uuid}
    e.g. cfe_nom_short_range_vpu08_init15_9469cd79-...

    The streamcommander resolves DAILY as:
      - If current_utc_hour < init_hour: use previous day
      - Else: use today
    """
    init_match = re.search(r'_init(\d{2})_', execution_name)
    if not init_match:
        return None

    init_hour = int(init_match.group(1))
    exec_date = original_start_time

    if exec_date.hour < init_hour:
        exec_date = exec_date - timedelta(days=1)

    return exec_date.strftime('%Y%m%d')


def replace_daily_with_date(input_data, date_str):
    """Replace DAILY with the resolved date in commands."""
    commands = input_data.get('commands', [])
    new_commands = []
    for cmd in commands:
        cmd = cmd.replace('ngen.DAILY', f'ngen.{date_str}')
        cmd = cmd.replace('/DAILY/', f'/{date_str}/')
        if '-s DAILY' in cmd:
            cmd = cmd.replace('-s DAILY', f'-s {date_str}0100 -e {date_str}0100')
        new_commands.append(cmd)
    input_data['commands'] = new_commands
    return input_data


def count_running_executions(state_machine_arn):
    """Count currently running executions to gauge load."""
    count = 0
    paginator = sfn_client.get_paginator('list_executions')
    for page in paginator.paginate(
        stateMachineArn=state_machine_arn,
        statusFilter='RUNNING',
        PaginationConfig={'MaxItems': 500}
    ):
        count += len(page['executions'])
    return count


def is_already_retried(state_machine_arn, original_name):
    """
    Check if a retry for this execution already exists (prevents duplicate retries
    from EventBridge redelivery or concurrent Lambda invocations).
    """
    base_name = re.sub(r'_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', '', original_name)

    # Check recent running and succeeded executions for a matching retry
    for status in ['RUNNING', 'SUCCEEDED']:
        try:
            response = sfn_client.list_executions(
                stateMachineArn=state_machine_arn,
                statusFilter=status,
                maxResults=50
            )
            for ex in response.get('executions', []):
                if ex['name'].startswith('auto_retry_') and base_name in ex['name']:
                    print(f"Found existing retry: {ex['name']} ({status})")
                    return True
        except Exception:
            pass
    return False


def lambda_handler(event, context):
    """
    Automatically retry failed Step Functions executions.
    Triggered by EventBridge rule on execution status change to FAILED.

    Key behaviors:
    - Waits RETRY_DELAY_SECONDS before retrying (avoids competing with scheduled batches)
    - Resolves DAILY dates based on the original execution's intended date
    - Checks current running execution count to avoid piling on during busy periods
    - Deduplicates retries to prevent multiple retries from EventBridge redelivery
    - Max 2 retries per execution
    """
    print(f"Received event: {json.dumps(event, default=str)}")

    detail = event.get('detail', {})
    execution_arn = detail.get('executionArn')
    state_machine_arn = detail.get('stateMachineArn')
    status = detail.get('status')
    execution_name = detail.get('name', '')

    if not execution_arn or status != 'FAILED':
        print(f"Skipping - not a failed execution. Status: {status}")
        return {'statusCode': 200, 'body': 'Skipped'}

    # Skip CI test executions — they have their own lifecycle
    if execution_name.startswith('ci_'):
        print(f"Skipping CI execution: {execution_name}")
        return {'statusCode': 200, 'body': 'Skipped CI execution'}

    # Skip retrying our own retry failures to prevent infinite loops
    if execution_name.startswith('auto_retry_'):
        retry_match = re.search(r'_r(\d+)_', execution_name)
        if retry_match and int(retry_match.group(1)) >= MAX_RETRIES:
            print(f"Max retries reached for {execution_name}. Not retrying.")
            return {'statusCode': 200, 'body': 'Max retries reached'}

    try:
        # Get original execution details
        execution = sfn_client.describe_execution(executionArn=execution_arn)
        original_input = execution.get('input', '{}')
        original_start = execution.get('startDate')

        input_data = json.loads(original_input)

        # Check retry count from input
        retry_count = input_data.get('auto_retry_count', 0)
        if retry_count >= MAX_RETRIES:
            print(f"Max retries ({MAX_RETRIES}) reached via input count. Not retrying.")
            return {'statusCode': 200, 'body': 'Max retries reached'}

        retry_num = retry_count + 1

        # Wait before retrying to let scheduled batches finish
        print(f"Waiting {RETRY_DELAY_SECONDS}s before retry to avoid impacting scheduled runs...")
        time.sleep(RETRY_DELAY_SECONDS)

        # Check if another invocation already retried this execution
        if is_already_retried(state_machine_arn, execution_name):
            print(f"Execution already retried by another invocation. Skipping.")
            return {'statusCode': 200, 'body': 'Already retried'}

        # Check current load
        running_count = count_running_executions(state_machine_arn)
        print(f"Currently {running_count} executions running")
        if running_count > MAX_RUNNING_THRESHOLD:
            print(f"High load ({running_count} running). Waiting additional {BUSY_WAIT_SECONDS}s...")
            time.sleep(BUSY_WAIT_SECONDS)

        # Resolve DAILY dates if present
        if any('DAILY' in cmd for cmd in input_data.get('commands', [])):
            intended_date = get_intended_date(execution_name, original_start)
            if intended_date:
                print(f"Resolving DAILY -> {intended_date} (from execution {execution_name})")
                input_data = replace_daily_with_date(input_data, intended_date)
            else:
                print(f"WARNING: Could not determine intended date from name: {execution_name}. DAILY will be re-resolved by streamcommander.")

        # Increment retry count
        input_data['auto_retry_count'] = retry_count + 1

        # Build retry execution name
        base_name = re.sub(r'_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', '', execution_name)
        base_name = re.sub(r'^auto_retry_r\d+_', '', base_name)
        new_name = f"auto_retry_r{retry_num}_{base_name}_{int(time.time())}"
        if len(new_name) > 80:
            new_name = new_name[:80]

        # Start retry execution
        response = sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=new_name,
            input=json.dumps(input_data)
        )

        new_arn = response['executionArn']
        print(f"Retry #{retry_num} started: {new_arn}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Execution retried',
                'failed_execution': execution_arn,
                'new_execution': new_arn,
                'retry_count': retry_num,
                'running_at_retry': running_count
            })
        }

    except Exception as e:
        print(f"Error retrying execution: {str(e)}")
        raise e
