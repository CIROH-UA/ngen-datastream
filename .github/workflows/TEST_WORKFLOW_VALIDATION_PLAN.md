# Test Workflow Validation Plan

## Overview
This document outlines the validation approach for the new test-isolated infrastructure deployment workflow (`infra_deploy_val.yaml`).

## Workflow Purpose
- **Test state machine functionality** with a single VPU execution
- **Validate infrastructure changes** without affecting dev/prod environments
- **Fast feedback loop** (~10-20 minutes vs hours for full validation)
- **Complete isolation** from ongoing builds

---

## Configuration Changes Summary

### New Files Created
1. **`infra/aws/terraform/backend-test.hcl`**
   - Separate Terraform state: `ngen-datastream/test/terraform.tfstate`
   - Region: `us-east-1`

2. **`infra/aws/terraform/variables-test.tfvars`**
   - All resources prefixed with `nrds_test_*`
   - SSM parameter: `/datastream/test/state-machine-arn`

### Modified Files
1. **`infra/aws/terraform/main.tf`**
   - Added `sm_parameter_name` variable (default: `/datastream/state-machine-arn`)
   - Passes parameter name to orchestration module

2. **`infra/aws/terraform/modules/orchestration/main.tf`**
   - SSM parameter name now configurable via `var.sm_parameter_name`

3. **`.github/workflows/infra_deploy_val.yaml`**
   - Environment: `test` (was `dev`)
   - Variables file: `variables-test.tfvars`
   - SSM parameter: `/datastream/test/state-machine-arn`
   - Single VPU test: VPU "01" only
   - Medium-range tests disabled (commented out)

---

## Resource Isolation

| Resource | Dev Environment | Test Environment |
|----------|----------------|------------------|
| State Machine | `nrds_dev_sm` | `nrds_test_sm` |
| State Machine Role | `nrds_dev_sm_role` | `nrds_test_sm_role` |
| SSM Parameter | `/datastream/state-machine-arn` | `/datastream/test/state-machine-arn` |
| Starter Lambda | `nrds_dev_start_ec2` | `nrds_test_start_ec2` |
| Commander Lambda | `nrds_dev_ec2_commander` | `nrds_test_ec2_commander` |
| Poller Lambda | `nrds_dev_ec2_command_poller` | `nrds_test_ec2_command_poller` |
| Checker Lambda | `nrds_dev_s3_object_checker` | `nrds_test_s3_object_checker` |
| Stopper Lambda | `nrds_dev_ec2_stopper` | `nrds_test_ec2_stopper` |
| Lambda Policy | `nrds_dev_lambda_policy` | `nrds_test_lambda_policy` |
| Lambda Role | `nrds_dev_lambda_role` | `nrds_test_lambda_role` |
| Lambda Invoke Policy | `nrds_dev_lambda_invoke_policy` | `nrds_test_lambda_invoke_policy` |
| EC2 Role | `nrds_dev_ec2_role` | `nrds_test_ec2_role` |
| EC2 Policy | `nrds_dev_ec2_policy` | `nrds_test_ec2_policy` |
| EC2 Instance Profile | `nrds_dev_ec2_profile` | `nrds_test_ec2_profile` |
| Terraform State | `terraform.tfstate` | `test/terraform.tfstate` |

---

## Workflow Jobs

### 1. `generate-executions`
- Generates VPU execution configuration files
- Uses Python script: `gen_vpu_execs.py`
- Creates ARM architecture execution files

### 2. `terraform-check`
- Terraform format validation
- Security scans (tfsec, Checkov)
- Terraform init, validate, plan
- Imports existing resources
- Uploads plan artifact

### 3. `terraform-apply`
- Runs only on `main` or `feature/infra-deployment` branches
- Re-generates execution files
- Downloads plan artifact
- Applies Terraform changes
- Waits 2 minutes for IAM propagation
- Uploads Terraform outputs

### 4. `test-short-range-vpus`
- **Tests single VPU**: VPU "01" only
- **Timeout**: 60 minutes
- **Run type**: short_range
- **Test date**: 20250905
- Steps:
  1. Generate execution file
  2. Modify for testing
  3. Create AWS key pair (if needed)
  4. Get state machine ARN from SSM
  5. Start Step Functions execution
  6. Monitor until completion
  7. Verify output files in S3
  8. Verify specific file (ngen-run.tar.gz)
  9. Clean up S3 test files

### 5. `terraform-destroy`
- Runs after tests complete (always runs, even on failure)
- Stops running Step Functions executions
- Terminates orphaned EC2 instances
- Destroys all Terraform-managed resources
- Verifies cleanup completion

---

## Pre-Run Validation Checklist

### ✅ Code Validation
- [x] Terraform configuration is valid
- [x] YAML syntax is correct
- [x] All variables defined in tfvars
- [x] Backend configuration correct

### ✅ Resource Naming
- [x] All test resources use `nrds_test_*` prefix
- [x] SSM parameter uses `/datastream/test/` prefix
- [x] State file uses `test/` subdirectory

### ✅ Workflow Configuration
- [x] Environment set to `test`
- [x] Variables file set to `variables-test.tfvars`
- [x] Backend config set to `backend-test.hcl`
- [x] Single VPU configured (VPU "01")
- [x] Medium-range tests disabled

---

## Manual Testing Checklist (During Workflow Run)

### Pre-Deployment
- [ ] Verify no `nrds_test_*` resources exist in AWS (clean slate)
- [ ] Check Terraform state file doesn't exist: `test/terraform.tfstate`
- [ ] Confirm no `/datastream/test/state-machine-arn` SSM parameter

### During Terraform Apply
- [ ] Monitor CloudFormation/Terraform output for resource creation
- [ ] Verify resources created with `nrds_test_*` naming
- [ ] Check IAM roles/policies created correctly
- [ ] Verify Lambda functions deployed
- [ ] Confirm State Machine created: `nrds_test_sm`
- [ ] Check SSM parameter created: `/datastream/test/state-machine-arn`

### During VPU Test Execution
- [ ] Verify Step Functions execution starts
- [ ] Monitor execution in AWS Step Functions console
- [ ] Check EC2 instance launches with test tags
- [ ] Verify instance uses `nrds_test_ec2_profile`
- [ ] Monitor CloudWatch logs for Lambda functions
- [ ] Check execution completes successfully

### Output Verification
- [ ] Verify S3 output files created in: `s3://ciroh-community-ngen-datastream/tests/short_range/VPU_01/`
- [ ] Confirm `ngen-run.tar.gz` exists and is accessible
- [ ] Check file count matches expectations

### During Terraform Destroy
- [ ] Verify Step Functions execution stopped (if running)
- [ ] Check orphaned EC2 instances terminated
- [ ] Monitor Terraform destroy output
- [ ] Confirm all resources deleted
- [ ] Verify SSM parameter removed
- [ ] Check Terraform state is empty

### Post-Cleanup Verification
- [ ] No `nrds_test_*` resources remain in AWS
- [ ] IAM roles/policies cleaned up
- [ ] Lambda functions removed
- [ ] State Machine deleted
- [ ] S3 test files cleaned up
- [ ] EC2 instances terminated
- [ ] CloudWatch log groups exist (but no active logs)

---

## Expected Behavior

### Success Criteria
1. ✅ All Terraform resources deploy successfully
2. ✅ State machine executes VPU 01 without errors
3. ✅ Output files generated in S3
4. ✅ All resources cleaned up after test
5. ✅ No conflicts with dev environment

### Failure Scenarios to Watch For

#### Scenario 1: Resource Name Conflicts
- **Symptom**: Terraform fails with "resource already exists"
- **Root Cause**: Test resources conflict with dev resources
- **Check**: Verify all names use `nrds_test_*` prefix
- **Fix**: Update variables-test.tfvars with unique names

#### Scenario 2: State File Conflicts
- **Symptom**: Terraform shows unexpected existing resources
- **Root Cause**: Using wrong backend state file
- **Check**: Verify `backend-test.hcl` is loaded
- **Fix**: Ensure `ENVIRONMENT=test` in workflow

#### Scenario 3: SSM Parameter Conflict
- **Symptom**: State machine ARN lookup fails or returns wrong ARN
- **Root Cause**: SSM parameter collision with dev
- **Check**: Verify using `/datastream/test/state-machine-arn`
- **Fix**: Update workflow SSM parameter paths

#### Scenario 4: VPU Execution Fails
- **Symptom**: Step Functions execution fails
- **Root Cause**: Various (permissions, configuration, etc.)
- **Debug Steps**:
  1. Check Step Functions execution logs
  2. Review CloudWatch logs for Lambda functions
  3. Verify EC2 instance has correct IAM role
  4. Check execution JSON configuration

#### Scenario 5: Cleanup Incomplete
- **Symptom**: Resources remain after terraform destroy
- **Root Cause**: Dependencies or dangling references
- **Check**: Run `terraform state list` to see remaining resources
- **Fix**: Manually terminate EC2 instances, delete resources, then retry destroy

---

## Validation Commands

### Check for Test Resources in AWS
```bash
# List all test Lambda functions
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `nrds_test_`)].FunctionName'

# List test IAM roles
aws iam list-roles --query 'Roles[?starts_with(RoleName, `nrds_test_`)].RoleName'

# List test state machines
aws stepfunctions list-state-machines --query 'stateMachines[?starts_with(name, `nrds_test_`)].name'

# Check test SSM parameter
aws ssm get-parameter --name "/datastream/test/state-machine-arn" --query 'Parameter.Value' --output text

# List test EC2 instances
aws ec2 describe-instances --filters "Name=iam-instance-profile.arn,Values=*nrds_test_ec2_profile*" --query 'Reservations[].Instances[].InstanceId'

# Check S3 test outputs
aws s3 ls s3://ciroh-community-ngen-datastream/tests/short_range/VPU_01/ --recursive
```

### Terraform State Verification
```bash
cd /Users/svemula1/Desktop/git/ngen-datastream/infra/aws/terraform

# Initialize with test backend
terraform init -backend-config=backend-test.hcl

# List resources in test state
terraform state list

# View specific resource
terraform state show <resource_name>

# Check state file directly (S3)
aws s3 ls s3://ciroh-terraform-state/ngen-datastream/test/
```

---

## Rollback Plan

If the workflow fails and cleanup doesn't complete:

### 1. Stop Running Executions
```bash
# Get state machine ARN
SM_ARN=$(aws ssm get-parameter --name "/datastream/test/state-machine-arn" --query 'Parameter.Value' --output text)

# List running executions
aws stepfunctions list-executions --state-machine-arn "$SM_ARN" --status-filter RUNNING

# Stop each execution
aws stepfunctions stop-execution --execution-arn <execution-arn>
```

### 2. Terminate EC2 Instances
```bash
# Find test instances
INSTANCE_IDS=$(aws ec2 describe-instances \
  --filters "Name=iam-instance-profile.arn,Values=*nrds_test_ec2_profile*" \
  --query 'Reservations[].Instances[].InstanceId' --output text)

# Terminate them
aws ec2 terminate-instances --instance-ids $INSTANCE_IDS
```

### 3. Manual Terraform Destroy
```bash
cd /Users/svemula1/Desktop/git/ngen-datastream/infra/aws/terraform
terraform init -backend-config=backend-test.hcl
terraform destroy -var-file=variables-test.tfvars -auto-approve
```

### 4. Clean S3 Test Files
```bash
aws s3 rm --recursive s3://ciroh-community-ngen-datastream/tests/short_range/VPU_01/
```

### 5. Remove SSM Parameter (if still exists)
```bash
aws ssm delete-parameter --name "/datastream/test/state-machine-arn"
```

---

## Next Steps After Validation

### If Validation Succeeds
1. ✅ Commit all changes to feature branch
2. ✅ Create PR with description of changes
3. ✅ Document workflow usage in repository README
4. ✅ Consider creating separate workflow for orchestration-only tests
5. ✅ Re-enable medium-range tests once issues are resolved

### If Validation Fails
1. 🔍 Review failure logs
2. 🔍 Check which scenario matches the failure
3. 🔧 Apply appropriate fix
4. 🔄 Re-run workflow
5. 📝 Update this document with lessons learned

---

## Future Enhancements

1. **Parameterize VPU Selection**
   - Allow manual VPU selection via workflow_dispatch inputs

2. **Add Notification**
   - Slack/email notifications on success/failure

3. **Performance Metrics**
   - Track execution time for each job
   - Compare against baselines

4. **Parallel Environment Testing**
   - Test multiple configurations simultaneously

5. **Automated Cleanup Verification**
   - Add job to verify complete cleanup
   - Alert if resources remain

---

## Contact

For questions or issues with this workflow:
- Check workflow logs in GitHub Actions
- Review AWS CloudWatch logs for detailed errors
- Contact: [Team Lead/DevOps Contact]

---

## Document History

- **2025-01-24**: Initial validation plan created
- **Version**: 1.0
- **Status**: Ready for First Run
