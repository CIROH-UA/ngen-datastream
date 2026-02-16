region                = "us-east-1"
scheduler_policy_name = "nrds_routing_only_deployment_scheduler_policy"
scheduler_role_name   = "nrds_routing_only_deployment_scheduler_role"

# Model AMI
routing_only_ami_id = "ami-0f8e27ecfe91ffd4f"

# Schedule Settings
schedule_timezone   = "America/New_York"
schedule_group_name = "default"
environment_suffix  = "routing_only"

# Remote state — shared orchestration
state_bucket            = "ciroh-terraform-state"
orchestration_state_key = "ngen-routing_only-datastream/terraform.tfstate"
