# Backend config for `terraform init -backend-config=envs/prod.backend.hcl`.
# Swap for `s3`, `http`, `gcs`, etc. as appropriate for your team.
# The local backend is the simplest starting point.

path = "terraform.prod.tfstate"
