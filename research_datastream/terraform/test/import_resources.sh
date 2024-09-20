#!/bin/bash
VAR_FILE="$1"
source $VAR_FILE

declare -A resource_map=(
  ["sm_name"]="stepfunctions|aws_sfn_state_machine.sm|list-state-machines --state-machine-name"
  ["starter_lambda_name"]="lambda|aws_lambda_function.starter_lambda|get-function --function-name"
  ["commander_lambda_name"]="lambda|aws_lambda_function.commander_lambda|get-function --function-name"
  ["poller_lambda_name"]="lambda|aws_lambda_function.poller_lambda|get-function --function-name"
  ["checker_lambda_name"]="lambda|aws_lambda_function.checker_lambda|get-function --function-name"
  ["stopper_lambda_name"]="lambda|aws_lambda_function.stopper_lambda|get-function --function-name"
  ["sm_role_name"]="iam|aws_iam_role.sm_role|get-role --role-name"
  ["lambda_role_name"]="iam|aws_iam_role.lambda_role|get-role --role-name"
  ["ec2_role"]="iam|aws_iam_role.ec2_role|get-role --role-name"
  ["lambda_policy_name"]="iam|aws_iam_policy.lambda_policy|list-policies --query 'Policies[?PolicyName==\`"
  ["lambda_invoke_policy_name"]="iam|aws_iam_policy.lambda_invoke_policy|list-policies --query 'Policies[?PolicyName==\`"
  ["ec2_policy_name"]="iam|aws_iam_policy.ec2_policy|list-policies --query 'Policies[?PolicyName==\`"
  ["profile_name"]="iam|aws_iam_instance_profile.ec2_profile|get-instance-profile --instance-profile-name"
)

import_resource() {
  local resource_type="$1"
  local resource_name="$2"
  local query_command="$3"
  local import_id="$4"

  echo "Checking for existing resource: $import_id"

  if aws $resource_type $query_command --region $region >/dev/null 2>&1; then
    echo "Resource $import_id exists, importing into Terraform state..."
    terraform import -var-file=$VAR_FILE $resource_name $import_id 
  else
    echo "Resource $import_id does not exist, skipping."
  fi
}

for var_name in "${!resource_map[@]}"; do
  resource_info=${resource_map[$var_name]}
  IFS='|' read -r resource_type tf_resource query_command <<< "$resource_info"
  
  resource_value=${!var_name}

  if [[ -n "$resource_value" ]]; then
    if [[ $query_command == *"Policies"* ]]; then
      query_command="$query_command$resource_value\`].Arn' --output text"
    else
      query_command="$query_command $resource_value"
    fi
    
    import_resource "$resource_type" "$tf_resource" "$query_command" "$resource_value"
  else
    echo "Variable $var_name is not set, skipping."
  fi
done

echo "Resource import process completed."
