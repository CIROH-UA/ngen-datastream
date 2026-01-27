region                    = "us-east-1"
sm_name                   = "nrds_dev_sm"
sm_role_name              = "nrds_dev_sm_role"
starter_lambda_name       = "nrds_dev_start_ec2"
commander_lambda_name     = "nrds_dev_ec2_commander"
poller_lambda_name        = "nrds_dev_ec2_command_poller"
checker_lambda_name       = "nrds_dev_s3_object_checker"
stopper_lambda_name       = "nrds_dev_ec2_stopper"
lambda_policy_name        = "nrds_dev_lambda_policy"
lambda_role_name          = "nrds_dev_lambda_role"
lambda_invoke_policy_name = "nrds_dev_lambda_invoke_policy"
ec2_role                  = "nrds_dev_ec2_role"
ec2_policy_name           = "nrds_dev_ec2_policy"
profile_name              = "nrds_dev_ec2_profile"
scheduler_policy_name     = "nrds_dev_scheduler_policy"
scheduler_role_name       = "nrds_dev_scheduler_role"

# EC2 Configuration
ec2_key_name         = "jlaser_community_east1"
ec2_security_groups  = ["sg-0fcbe0c6d6faa0117"]
ec2_instance_profile = "datastream_community_ec2_profile"

# Model AMIs
cfe_nom_ami_id = "ami-0ef008a1e6d9aa12d"
lstm_ami_id    = "ami-0bba768785947ef54"

# Schedule Settings
schedule_timezone   = "America/New_York"
schedule_group_name = "default"
environment_suffix  = "test"
