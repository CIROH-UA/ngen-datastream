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

# Usage: get_console_output INSTANCE_ID
# Prints what the instance has written to its console so far.
get_console_output() {
  aws ec2 get-console-output --instance-id "$1" --latest --query Output --output text | tr -d '\r'
}

# Usage: wait_for_result_in_console INSTANCE_ID RESULT_NAME TIMEOUT_MINUTES
# Checks the console every 30 seconds until a "RESULT_NAME=..." line appears and prints the log
wait_for_result_in_console() {
  instance_id=$1
  result_name=$2
  timeout_minutes=$3
  started_at=$(date +%s)
  while true; do
    console_output=$(get_console_output "$instance_id") || return 1
    result_line=$(echo "$console_output" | grep -a -o "$result_name=.*" | tail -n 1 || true)
    if [ -n "$result_line" ]; then
      echo "${result_line#*=}"
      return 0
    fi

    minutes_waited=$(( ($(date +%s) - started_at) / 60 ))
    if [ "$minutes_waited" -ge "$timeout_minutes" ]; then
      echo "missing"
      return 0
    fi
    log "$instance_id ($minutes_waited min): $(echo "$console_output" | tail -n 1)" >&2
    sleep 30
  done
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
