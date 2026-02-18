region = "us-east-1"

# Orchestration
resource_prefix           = "nrds_routing_only_test"
sm_name                   = "nrds_routing_only_test_sm"
sm_role_name              = "nrds_routing_only_test_sm_role"
starter_lambda_name       = "nrds_routing_only_test_start_ec2"
commander_lambda_name     = "nrds_routing_only_test_ec2_commander"
poller_lambda_name        = "nrds_routing_only_test_ec2_command_poller"
checker_lambda_name       = "nrds_routing_only_test_s3_object_checker"
stopper_lambda_name       = "nrds_routing_only_test_ec2_stopper"
lambda_policy_name        = "nrds_routing_only_test_lambda_policy"
lambda_role_name          = "nrds_routing_only_test_lambda_role"
lambda_invoke_policy_name = "nrds_routing_only_test_lambda_invoke_policy"
ec2_role                  = "nrds_routing_only_test_ec2_role"
ec2_policy_name           = "nrds_routing_only_test_ec2_policy"
profile_name              = "nrds_routing_only_test_ec2_profile"

# Scheduler
scheduler_policy_name = "nrds_routing_only_test_scheduler_policy"
scheduler_role_name   = "nrds_routing_only_test_scheduler_role"

# Model AMI
routing_only_ami_id = "ami-0f8e27ecfe91ffd4f"

# Schedule Settings
schedule_timezone   = "America/New_York"
schedule_group_name = "default"
environment_suffix  = "test"

# S3
s3_bucket = "ciroh-community-ngen-datastream"
