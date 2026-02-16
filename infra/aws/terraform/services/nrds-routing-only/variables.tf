variable "region" {
  type        = string
  description = "AWS region"
}

# Remote state configuration
variable "state_bucket" {
  type        = string
  description = "S3 bucket containing the shared orchestration state file"
}

variable "orchestration_state_key" {
  type        = string
  description = "S3 key for the shared orchestration state file"
}

# Scheduler IAM
variable "scheduler_policy_name" {
  type        = string
  description = "Name of the scheduler IAM policy"
}

variable "scheduler_role_name" {
  type        = string
  description = "Name of the scheduler IAM role"
}

# Model-specific AMIs
variable "routing_only_ami_id" {
  type        = string
  description = "AMI ID for Routing-Only model EC2 instances"
  default     = "ami-0f8e27ecfe91ffd4f"
}

# Schedule Settings
variable "schedule_timezone" {
  type        = string
  description = "Timezone for EventBridge schedules"
  default     = "America/New_York"
}

variable "schedule_group_name" {
  type        = string
  description = "EventBridge scheduler group name"
  default     = "default"
}

variable "environment_suffix" {
  type        = string
  description = "Environment suffix for schedule names (e.g., 'dev', 'prod', 'test')"
}
