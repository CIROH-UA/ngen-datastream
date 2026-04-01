#!/bin/bash
set -e

# Cleanup on failure — terminate instance if script fails mid-way
cleanup() {
    if [[ -n "$INSTANCE_ID" ]]; then
        echo "Cleaning up... terminating instance $INSTANCE_ID" >&2
        aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID" 2>/dev/null || true
    fi
    rm -f /tmp/user_data_script.sh
}
trap cleanup ERR

# Configuration
REGION="us-east-1"
INSTANCE_TYPE="t4g.large"

# Get the latest Amazon Linux 2023 ARM64 AMI ID dynamically
BASE_AMI=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 --region "$REGION" --query "Parameter.Value" --output text)

KEY_NAME="actions_key_arm"
SECURITY_GROUP="sg-0fcbe0c6d6faa0117"
IAM_ROLE_NAME="AmiBuilderSSMRole"
IAM_INSTANCE_PROFILE="Name=$IAM_ROLE_NAME"

# Ensure IAM role and instance profile exist for SSM access
if ! aws iam get-instance-profile --instance-profile-name "$IAM_ROLE_NAME" >/dev/null 2>&1; then
    echo "Creating IAM role and instance profile: $IAM_ROLE_NAME..." >&2

    # Create the IAM role with EC2 trust policy
    aws iam create-role \
        --role-name "$IAM_ROLE_NAME" \
        --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }' >/dev/null

    # Attach the SSM managed policy
    aws iam attach-role-policy \
        --role-name "$IAM_ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"

    # Create instance profile and add the role
    aws iam create-instance-profile \
        --instance-profile-name "$IAM_ROLE_NAME" >/dev/null
    aws iam add-role-to-instance-profile \
        --instance-profile-name "$IAM_ROLE_NAME" \
        --role-name "$IAM_ROLE_NAME"

    # Wait for IAM propagation
    echo "Waiting for IAM instance profile to propagate..." >&2
    sleep 10
else
    echo "IAM instance profile $IAM_ROLE_NAME already exists." >&2
fi

# Use environment variables passed from workflow (with defaults)
AMI_NAME="${AMI_NAME:-ami_tag}"
DS_TAG="${DS_TAG:-latest}"
FP_TAG="${FP_TAG:-latest}"
NGIAB_TAG="${NGIAB_TAG:-latest}"

# Check for duplicate AMI name before launching an instance
EXISTING_AMI=$(aws ec2 describe-images \
    --region "$REGION" \
    --owners self \
    --filters "Name=name,Values=$AMI_NAME" \
    --query 'Images[0].ImageId' \
    --output text 2>/dev/null)

if [[ -n "$EXISTING_AMI" && "$EXISTING_AMI" != "None" ]]; then
    echo "ERROR: AMI name '$AMI_NAME' is already in use by $EXISTING_AMI." >&2
    echo "Use a different AMI_NAME or deregister the existing AMI first." >&2
    exit 1
fi

echo "Creating AMI with key pair: $KEY_NAME and security group: $SECURITY_GROUP" >&2
echo "Using base AMI: $BASE_AMI" >&2
echo "AMI Name: $AMI_NAME" >&2
echo "Tags: DS_TAG=$DS_TAG, FP_TAG=$FP_TAG, NGIAB_TAG=$NGIAB_TAG" >&2

# Create user data script using a here document for better formatting
cat > /tmp/user_data_script.sh << 'USER_DATA_EOF'
#!/bin/bash
exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "Starting user data execution at $(date)"

# Set the actual tag values from workflow
USER_DATA_EOF

# Add the environment variables to the script
cat >> /tmp/user_data_script.sh << USER_DATA_VARS
export DS_TAG='$DS_TAG'
export FP_TAG='$FP_TAG'
export NGIAB_TAG='$NGIAB_TAG'

echo "Starting setup with tags: DS_TAG=\$DS_TAG, FP_TAG=\$FP_TAG, NGIAB_TAG=\$NGIAB_TAG"

USER_DATA_VARS

# Add the rest of the setup script
cat >> /tmp/user_data_script.sh << 'USER_DATA_SETUP'
echo "Updating system packages..."
dnf update -y

echo "Installing packages..."
dnf install -y git docker python3-pip pigz awscli tar wget

echo "Starting Docker service..."
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

echo "Waiting for Docker to be ready..."
sleep 10

echo "Writing optimized Docker daemon configuration..."
cat > /etc/docker/daemon.json << 'DOCKER_CONF'
{
  "storage-driver": "overlay2",
  "log-driver": "local",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "live-restore": true,
  "default-ulimits": {
    "nofile": { "Name": "nofile", "Hard": 65536, "Soft": 65536 }
  }
}
DOCKER_CONF

echo "Restarting Docker with optimized config..."
systemctl restart docker
sleep 5

echo "Installing Docker Compose..."
# Install Docker Compose v2 for ARM64 (pinned version for reproducibility)
COMPOSE_VERSION="v2.32.4"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-aarch64" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Create symlink for backward compatibility
ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/bin/docker-compose

echo "Verifying Docker Compose installation..."
docker compose version

echo "Installing hfsubset..."
cd /tmp
curl -L -O https://github.com/lynker-spatial/hfsubsetCLI/releases/download/v1.1.0/hfsubset-v1.1.0-linux_arm64.tar.gz
tar -xzvf hfsubset-v1.1.0-linux_arm64.tar.gz
mv ./hfsubset /usr/bin/hfsubset
chmod +x /usr/bin/hfsubset

echo "Cloning ngen-datastream repository..."
cd /home/ec2-user
sudo -u ec2-user git clone https://github.com/CIROH-UA/ngen-datastream.git
chown -R ec2-user:ec2-user /home/ec2-user/ngen-datastream

echo "Cloning datastreamcli repository..."
sudo -u ec2-user git clone https://github.com/CIROH-UA/datastreamcli.git
chown -R ec2-user:ec2-user /home/ec2-user/datastreamcli

echo "Pulling Docker images..."
docker pull awiciroh/datastream:$DS_TAG
docker pull awiciroh/forcingprocessor:$FP_TAG
docker pull awiciroh/ciroh-ngen-image:$NGIAB_TAG
docker pull zwills/merkdir

echo "Pre-warming Docker runtime..."
docker run --rm awiciroh/datastream:$DS_TAG echo "warm"
docker run --rm awiciroh/forcingprocessor:$FP_TAG echo "warm"
docker run --rm awiciroh/ciroh-ngen-image:$NGIAB_TAG echo "warm"
echo "Docker pre-warm complete"

echo "=== Setup completed successfully at $(date) ===" > /var/log/setup-complete
echo "Setup completed successfully!"
USER_DATA_SETUP

# Launch instance
echo "Launching EC2 instance..."
INSTANCE_ID=$(aws ec2 run-instances \
    --region "$REGION" \
    --image-id "$BASE_AMI" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SECURITY_GROUP" \
    --iam-instance-profile "$IAM_INSTANCE_PROFILE" \
    --user-data file:///tmp/user_data_script.sh \
    --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":32,"VolumeType":"gp3"}}]' \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "Instance ID: $INSTANCE_ID"

# Tag instance for identification in the console
aws ec2 create-tags --region "$REGION" --resources "$INSTANCE_ID" \
    --tags Key=Name,Value="ami-builder-$AMI_NAME"

# Wait for running and setup
echo "Waiting for instance to be running..."
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"

echo "Waiting for setup to complete (polling via SSM, up to 30 minutes)..."
# Poll for setup-complete marker instead of a fixed sleep
MAX_ATTEMPTS=60
POLL_INTERVAL=30
SETUP_COMPLETE=false
for i in $(seq 1 "$MAX_ATTEMPTS"); do
    COMMAND_ID=$(aws ssm send-command \
        --region "$REGION" \
        --instance-ids "$INSTANCE_ID" \
        --document-name "AWS-RunShellScript" \
        --parameters 'commands=["cat /var/log/setup-complete 2>/dev/null || echo NOT_READY"]' \
        --query 'Command.CommandId' \
        --output text 2>/dev/null) || { sleep "$POLL_INTERVAL"; continue; }

    sleep 5  # brief wait for command to execute

    OUTPUT=$(aws ssm get-command-invocation \
        --region "$REGION" \
        --command-id "$COMMAND_ID" \
        --instance-id "$INSTANCE_ID" \
        --query 'StandardOutputContent' \
        --output text 2>/dev/null) || { sleep "$POLL_INTERVAL"; continue; }

    if echo "$OUTPUT" | grep -q "Setup completed successfully"; then
        echo "Setup completed on instance."
        SETUP_COMPLETE=true
        break
    fi

    echo "  Attempt $i/$MAX_ATTEMPTS — setup still in progress..."
    sleep "$POLL_INTERVAL"
done

if [[ "$SETUP_COMPLETE" != "true" ]]; then
    echo "ERROR: Setup did not complete within the timeout period." >&2
    exit 1
fi

# Stop instance
echo "Stopping instance..."
aws ec2 stop-instances --region "$REGION" --instance-ids "$INSTANCE_ID" >/dev/null
aws ec2 wait instance-stopped --region "$REGION" --instance-ids "$INSTANCE_ID"

# Create AMI
echo "Creating AMI: $AMI_NAME"
AMI_ID=$(aws ec2 create-image \
    --region "$REGION" \
    --instance-id "$INSTANCE_ID" \
    --name "$AMI_NAME" \
    --description "ngen-datastream AMI with DS_TAG=$DS_TAG, FP_TAG=$FP_TAG, NGIAB_TAG=$NGIAB_TAG" \
    --query 'ImageId' \
    --output text)

if [[ -z "$AMI_ID" ]]; then
    echo "ERROR: Failed to create AMI — no AMI ID returned." >&2
    exit 1
fi

echo "AMI ID: $AMI_ID"

# Wait for AMI
echo "Waiting for AMI to be available..."
aws ec2 wait image-available --region "$REGION" --image-ids "$AMI_ID"

# Cleanup
echo "Terminating instance..."
aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID" >/dev/null

# Clean up temporary file
rm -f /tmp/user_data_script.sh

# Output only the AMI ID
echo "$AMI_ID"
