#!/bin/bash
set -e

# Configuration
REGION="us-east-1"
INSTANCE_TYPE="t4g.large"

# Get the latest Amazon Linux 2023 ARM64 AMI ID dynamically
BASE_AMI=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 --region "$REGION" --query "Parameter.Value" --output text)

KEY_NAME="actions_key_arm"
SECURITY_GROUP="sg-0fcbe0c6d6faa0117"

# Use environment variables passed from workflow (with defaults)
AMI_NAME="${AMI_NAME:-ami_tag}"
DS_TAG="${DS_TAG:-latest}"
FP_TAG="${FP_TAG:-latest}"
NGIAB_TAG="${NGIAB_TAG:-latest}"

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

echo "Installing git..."
dnf install -y git
dnf install -y docker
dnf install -y python3-pip pigz awscli tar wget

echo "Starting Docker service..."
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

echo "Waiting for Docker to be ready..."
sleep 10

echo "Installing Docker Compose..."
# Install Docker Compose v2 for ARM64
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-aarch64 -o /usr/local/lib/docker/cli-plugins/docker-compose
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

echo "Pulling Docker images..."
docker pull awiciroh/datastream:$DS_TAG
docker pull awiciroh/forcingprocessor:$FP_TAG
docker pull awiciroh/ciroh-ngen-image:$NGIAB_TAG

echo "=== Setup completed successfully at $(date) ===" > /var/log/setup-complete
echo "Setup completed successfully!"
USER_DATA_SETUP

# Read the complete user data script
USER_DATA=$(cat /tmp/user_data_script.sh)

# Launch instance
echo "Launching EC2 instance..."
INSTANCE_ID=$(aws ec2 run-instances \
    --region "$REGION" \
    --image-id "$BASE_AMI" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SECURITY_GROUP" \
    --user-data file:///tmp/user_data_script.sh \
    --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":32,"VolumeType":"gp3"}}]' \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "Instance ID: $INSTANCE_ID"

# Wait for running and setup
echo "Waiting for instance to be running..."
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"

echo "Waiting 20 minutes for setup to complete..."
sleep 1200  # 10 minutes for setup

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
