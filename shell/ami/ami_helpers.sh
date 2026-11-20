#!/bin/bash
# Functions in this file are used by create_ami.sh and test_ami.sh.

export AWS_REGION="${AWS_REGION:-us-east-1}"

SECURITY_GROUP_ID="sg-0fcbe0c6d6faa0117"

# Every instance gets this tag so the workflow can find and terminate any instance later
WORKFLOW_RUN_TAG_KEY="ami-workflow-run"
WORKFLOW_RUN="${WORKFLOW_RUN:-local-$(date +%s)}"

log() {
  echo "[$(date -u +%H:%M:%S)] $*"
}

# Usage: write_user_data OUTPUT_FILE SCRIPT VARIABLE_NAME...
# Uses to set environment variables in the instance
write_user_data() {
  output_file=$1
  script=$2
  shift 2
  {
    echo "#!/bin/bash"
    for variable_name in "$@"; do
      declare -p "$variable_name"
    done
    cat "$script"
  } > "$output_file"
}

# Usage: wait_for_instance_to_stop INSTANCE_ID TIMEOUT_MINUTES
wait_for_instance_to_stop() {
  instance_id=$1
  timeout_minutes=$2
  started_at=$(date +%s)
  while true; do
    state=$(aws ec2 describe-instances --instance-ids "$instance_id" \
      --query 'Reservations[0].Instances[0].State.Name' --output text)
    minutes_waited=$(( ($(date +%s) - started_at) / 60 ))
    log "$instance_id is $state ($minutes_waited min)"

    if [ "$state" = "stopped" ]; then
      return 0
    fi
    if [ "$state" = "terminated" ] || [ "$state" = "shutting-down" ]; then
      log "ERROR: $instance_id was terminated before it finished"
      return 1
    fi
    if [ "$minutes_waited" -ge "$timeout_minutes" ]; then
      log "ERROR: $instance_id did not stop within $timeout_minutes minutes"
      return 1
    fi
    sleep 30
  done
}

# Usage: get_console_output INSTANCE_ID
# Prints what the instance wrote to its serial console 
get_console_output() {
  aws ec2 get-console-output --instance-id "$1" --latest --query Output --output text | tr -d '\r'
}

# Usage: read_result_from_console INSTANCE_ID RESULT_NAME
# Finds the last "RESULT_NAME=..." line in the console and prints the part after "=".
# Prints "missing" if the line never shows up.
read_result_from_console() {
  instance_id=$1
  result_name=$2
  # The console can lag a little behind the instance, so try for a few minutes.
  for attempt in 1 2 3 4 5 6; do
    result_line=$(get_console_output "$instance_id" | grep -a -o "$result_name=.*" | tail -n 1 || true)
    if [ -n "$result_line" ]; then
      echo "${result_line#*=}"
      return 0
    fi
    sleep 30
  done
  echo "missing"
}

# Usage: terminate_instance INSTANCE_ID
terminate_instance() {
  instance_id=$1
  if [ -z "$instance_id" ]; then
    return 0
  fi
  log "Terminating $instance_id"
  aws ec2 terminate-instances --instance-ids "$instance_id" > /dev/null \
    || log "WARNING: could not terminate $instance_id, please terminate it by hand"
}
