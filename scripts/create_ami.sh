#!/bin/bash
set -e
# Configuration
REGION="us-east-1"
INSTANCE_TYPE="t4g.large"
# Get the latest Amazon Linux 2023 ARM64 AMI ID dynamically
BASE_AMI=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 --region "$REGION" --query "Parameter.Value" --output text)
KEY_NAME="actions_key_arm"
SECURITY_GROUP="sg-0fcbe0c6d6faa0117"
AMI_NAME="ami_tag"
echo "Creating AMI with key pair: $KEY_NAME and security group: $SECURITY_GROUP" >&2
echo "Using base AMI: $BASE_AMI" >&2
USER_DATA='#!/bin/bash
exec > >(tee /var/log/user-data.log)
exec 2>&1
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
echo "Updating datastream script with placeholder tags..."
sed -i '\''s|DS_TAG=${DS_TAG:-"latest"}|DS_TAG=${DS_TAG:-"ds_tag_from_workflow"}|'\'' /home/ec2-user/ngen-datastream/scripts/datastream
sed -i '\''s|FP_TAG=${FP_TAG:-"latest"}|FP_TAG=${FP_TAG:-"fp_tag_from_workflow"}|'\'' /home/ec2-user/ngen-datastream/scripts/datastream
sed -i '\''s|NGIAB_TAG=${NGIAB_TAG:-"latest"}|NGIAB_TAG=${NGIAB_TAG:-"ngiab_tag_from_workflow"}|'\'' /home/ec2-user/ngen-datastream/scripts/datastream
grep -E "(DS_TAG|FP_TAG|NGIAB_TAG)" /home/ec2-user/ngen-datastream/scripts/datastream
echo "=== Setup completed successfully at $(date) ===" > /var/log/setup-complete
echo "Setup completed successfully!"
'
# Launch instance
INSTANCE_ID=$(aws ec2 run-instances \
    --region "$REGION" \
    --image-id "$BASE_AMI" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SECURITY_GROUP" \
    --user-data "$USER_DATA" \
    --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":32,"VolumeType":"gp3"}}]' \
    --query 'Instances[0].InstanceId' \
    --output text)
# Wait for running and setup
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"
sleep 900  # 15 minutes for setup
# Stop instance
aws ec2 stop-instances --region "$REGION" --instance-ids "$INSTANCE_ID" >/dev/null
aws ec2 wait instance-stopped --region "$REGION" --instance-ids "$INSTANCE_ID"
# Create AMI
AMI_ID=$(aws ec2 create-image \
    --region "$REGION" \
    --instance-id "$INSTANCE_ID" \
    --name "$AMI_NAME" \
    --description "ngen-datastream AMI" \
    --query 'ImageId' \
    --output text)
# Wait for AMI
aws ec2 wait image-available --region "$REGION" --image-ids "$AMI_ID"
# Cleanup
aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID" >/dev/null
# Output only the AMI ID
echo "$AMI_ID"