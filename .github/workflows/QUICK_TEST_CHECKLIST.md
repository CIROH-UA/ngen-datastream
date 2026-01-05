# Quick Test Workflow Checklist

## Before Running Workflow

### Pre-Flight Check
```bash
# 1. Verify no test resources exist
aws stepfunctions list-state-machines --query 'stateMachines[?starts_with(name, `nrds_test_`)].name'
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `nrds_test_`)].FunctionName'
aws iam list-roles --query 'Roles[?starts_with(RoleName, `nrds_test_`)].RoleName'

# 2. Check SSM parameter doesn't exist
aws ssm get-parameter --name "/datastream/test/state-machine-arn" 2>&1 | grep -q "ParameterNotFound" && echo "✓ SSM parameter doesn't exist" || echo "✗ SSM parameter exists!"

# 3. Verify state file doesn't exist
aws s3 ls s3://ciroh-terraform-state/ngen-datastream/test/terraform.tfstate 2>&1 | grep -q "NoSuchKey" && echo "✓ State file doesn't exist" || echo "✗ State file exists!"
```

---

## During Workflow Execution

### Monitor These AWS Resources

#### 1. CloudFormation/Terraform
- Watch for `nrds_test_*` resource creation
- Check for any errors in Terraform output

#### 2. Step Functions Console
- Go to: https://console.aws.amazon.com/states/home?region=us-east-1
- Look for state machine: `nrds_test_sm`
- Monitor execution: `sr-vpu-01-*`

#### 3. EC2 Console
- Go to: https://console.aws.amazon.com/ec2/home?region=us-east-1
- Filter by IAM instance profile: `nrds_test_ec2_profile`
- Verify instance launches and terminates

#### 4. Lambda Console
- Go to: https://console.aws.amazon.com/lambda/home?region=us-east-1
- Check functions: `nrds_test_start_ec2`, `nrds_test_ec2_commander`, etc.
- Monitor CloudWatch logs for errors

#### 5. S3 Bucket
- Go to: https://s3.console.aws.amazon.com/s3/buckets/ciroh-community-ngen-datastream
- Navigate to: `tests/short_range/VPU_01/`
- Verify `ngen-run.tar.gz` appears

---

## After Workflow Completes

### Post-Run Verification
```bash
# 1. Verify all test resources cleaned up
aws stepfunctions list-state-machines --query 'stateMachines[?starts_with(name, `nrds_test_`)].name'
# Expected: []

aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `nrds_test_`)].FunctionName'
# Expected: []

aws iam list-roles --query 'Roles[?starts_with(RoleName, `nrds_test_`)].RoleName'
# Expected: []

# 2. Check SSM parameter removed
aws ssm get-parameter --name "/datastream/test/state-machine-arn" 2>&1 | grep -q "ParameterNotFound" && echo "✓ Cleaned up" || echo "✗ Still exists!"

# 3. Verify no orphaned EC2 instances
aws ec2 describe-instances \
  --filters "Name=iam-instance-profile.arn,Values=*nrds_test_ec2_profile*" \
  --query 'Reservations[].Instances[?State.Name!=`terminated`].InstanceId'
# Expected: []

# 4. Check S3 test files cleaned up
aws s3 ls s3://ciroh-community-ngen-datastream/tests/short_range/VPU_01/ 2>&1
# Expected: No objects found

# 5. Verify Terraform state empty
cd /Users/svemula1/Desktop/git/ngen-datastream/infra/aws/terraform
terraform init -backend-config=backend-test.hcl -reconfigure
terraform state list
# Expected: No resources
```

---

## Common Issues & Quick Fixes

### Issue: Workflow fails at Terraform Apply
**Check:**
```bash
# View workflow logs in GitHub Actions
# Look for resource conflicts or permission errors
```
**Fix:**
- Check if resources already exist with `nrds_test_*` names
- Verify AWS credentials have correct permissions
- Ensure backend state file is accessible

### Issue: VPU Test Execution Fails
**Check:**
```bash
# Get execution ARN from workflow logs, then:
aws stepfunctions describe-execution --execution-arn <arn> --region us-east-1
```
**Fix:**
- Review Step Functions execution history
- Check CloudWatch logs for Lambda errors
- Verify execution JSON configuration

### Issue: Terraform Destroy Fails
**Check:**
```bash
terraform init -backend-config=backend-test.hcl -reconfigure
terraform state list
```
**Manual Cleanup:**
```bash
# Stop executions
SM_ARN=$(aws ssm get-parameter --name "/datastream/test/state-machine-arn" --query 'Parameter.Value' --output text)
aws stepfunctions list-executions --state-machine-arn "$SM_ARN" --status-filter RUNNING | \
  jq -r '.executions[].executionArn' | \
  xargs -I {} aws stepfunctions stop-execution --execution-arn {}

# Terminate instances
aws ec2 describe-instances \
  --filters "Name=iam-instance-profile.arn,Values=*nrds_test_ec2_profile*" \
  --query 'Reservations[].Instances[].InstanceId' --output text | \
  xargs -I {} aws ec2 terminate-instances --instance-ids {}

# Wait 2 minutes for cleanup, then retry destroy
sleep 120
terraform destroy -var-file=variables-test.tfvars -auto-approve
```

---

## Success Criteria

- ✅ Workflow completes all jobs (green checkmarks)
- ✅ VPU 01 execution succeeds
- ✅ Output files created in S3
- ✅ All resources cleaned up
- ✅ No orphaned instances
- ✅ Zero test resources remain in AWS

---

## Quick Reference: Important URLs

- **GitHub Actions**: `https://github.com/<org>/<repo>/actions/workflows/infra_deploy_val.yaml`
- **Step Functions**: `https://console.aws.amazon.com/states/home?region=us-east-1`
- **EC2 Instances**: `https://console.aws.amazon.com/ec2/home?region=us-east-1`
- **Lambda Functions**: `https://console.aws.amazon.com/lambda/home?region=us-east-1`
- **S3 Bucket**: `https://s3.console.aws.amazon.com/s3/buckets/ciroh-community-ngen-datastream`
- **CloudWatch Logs**: `https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups`

---

## Timeline Expectations

- **generate-executions**: ~2-3 minutes
- **terraform-check**: ~5-10 minutes
- **terraform-apply**: ~5-10 minutes
- **IAM propagation wait**: 2 minutes
- **test-short-range-vpus**: ~10-20 minutes
- **terraform-destroy**: ~5-10 minutes

**Total Expected Time**: ~30-55 minutes

---

## Emergency Stop

If you need to stop the workflow immediately:

1. **Cancel workflow in GitHub Actions**
2. **Stop Step Functions executions**:
   ```bash
   SM_ARN=$(aws ssm get-parameter --name "/datastream/test/state-machine-arn" --query 'Parameter.Value' --output text)
   aws stepfunctions list-executions --state-machine-arn "$SM_ARN" --status-filter RUNNING --query 'executions[*].executionArn' --output text | xargs -I {} aws stepfunctions stop-execution --execution-arn {}
   ```
3. **Terminate instances**:
   ```bash
   aws ec2 describe-instances --filters "Name=iam-instance-profile.arn,Values=*nrds_test_ec2_profile*" "Name=instance-state-name,Values=running,pending" --query 'Reservations[].Instances[].InstanceId' --output text | xargs -I {} aws ec2 terminate-instances --instance-ids {}
   ```
4. **Run manual cleanup** (see manual cleanup section above)
