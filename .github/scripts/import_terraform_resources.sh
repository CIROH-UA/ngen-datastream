#!/bin/bash
set -e

# Simple Terraform Resource Import Script
# Imports existing AWS resources into Terraform state to prevent "EntityAlreadyExists" errors

echo "=========================================="
echo "Terraform Resource Import Script"
echo "=========================================="

# Determine environment (default to dev if not set)
ENV=${ENVIRONMENT:-dev}
echo "Environment: $ENV"

# Set backend and vars file based on environment
if [ "$ENV" = "test" ]; then
  BACKEND_CONFIG="backend-test.hcl"
  VARS_FILE="variables-test.tfvars"
  PREFIX="nrds_test"
else
  BACKEND_CONFIG="backend-dev.hcl"
  VARS_FILE="variables.tfvars"
  PREFIX="nrds_dev"
fi

# Get AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "Backend Config: $BACKEND_CONFIG"
echo "Variables File: $VARS_FILE"
echo "Resource Prefix: $PREFIX"
echo ""

# Initialize Terraform with appropriate backend
echo "Initializing Terraform..."
terraform init -backend-config=$BACKEND_CONFIG
echo ""

# Import function - tries to import, ignores if already exists or not found
import_resource() {
  local resource="$1"
  local id="$2"
  echo "Importing $resource..."
  terraform import -var-file=$VARS_FILE "$resource" "$id" 2>&1 | grep -v "Resource already managed" || true
}

echo "Starting imports..."
echo ""

# IAM Roles
import_resource "module.nrds_orchestration.aws_iam_role.ec2_role" "${PREFIX}_ec2_role"
import_resource "module.nrds_orchestration.aws_iam_role.lambda_role" "${PREFIX}_lambda_role"
import_resource "module.nrds_orchestration.aws_iam_role.iam_for_sfn" "${PREFIX}_sm_role"

# IAM Policies
import_resource "module.nrds_orchestration.aws_iam_policy.ec2_policy" "arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${PREFIX}_ec2_policy"
import_resource "module.nrds_orchestration.aws_iam_policy.datastreamlambda_policy" "arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${PREFIX}_lambda_policy"
import_resource "module.nrds_orchestration.aws_iam_policy.lambda_invoke_policy" "arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${PREFIX}_lambda_invoke_policy"

# IAM Role Policy Attachments
import_resource "module.nrds_orchestration.aws_iam_role_policy_attachment.ec2_role_custom_policy_attach" "${PREFIX}_ec2_role/arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${PREFIX}_ec2_policy"
import_resource "module.nrds_orchestration.aws_iam_role_policy_attachment.ssm_policy_attachment" "${PREFIX}_ec2_role/arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
import_resource "module.nrds_orchestration.aws_iam_role_policy_attachment.datastream_attachment" "${PREFIX}_lambda_role/arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${PREFIX}_lambda_policy"
import_resource "module.nrds_orchestration.aws_iam_role_policy_attachment.ssm_policy_attachment2" "${PREFIX}_lambda_role/arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
import_resource "module.nrds_orchestration.aws_iam_role_policy_attachment.sm_invoke_lambda_attach" "${PREFIX}_sm_role/arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${PREFIX}_lambda_invoke_policy"

# IAM Instance Profile
import_resource "module.nrds_orchestration.aws_iam_instance_profile.instance_profile" "${PREFIX}_ec2_profile"

# Lambda Functions (if they exist)
import_resource "module.nrds_orchestration.aws_lambda_function.starter_lambda" "${PREFIX}_start_ec2"
import_resource "module.nrds_orchestration.aws_lambda_function.commander_lambda" "${PREFIX}_ec2_commander"
import_resource "module.nrds_orchestration.aws_lambda_function.poller_lambda" "${PREFIX}_ec2_command_poller"
import_resource "module.nrds_orchestration.aws_lambda_function.checker_lambda" "${PREFIX}_s3_object_checker"
import_resource "module.nrds_orchestration.aws_lambda_function.stopper_lambda" "${PREFIX}_ec2_stopper"

# Step Functions State Machine (if it exists)
SM_ARN=$(aws stepfunctions list-state-machines --query "stateMachines[?name=='${PREFIX}_sm'].stateMachineArn" --output text --region us-east-1 2>/dev/null || echo "")
if [ -n "$SM_ARN" ]; then
  import_resource "module.nrds_orchestration.aws_sfn_state_machine.sm" "$SM_ARN"
fi

echo ""
echo "=========================================="
echo "Import Complete!"
echo "=========================================="
echo "Run 'terraform plan' to verify"
