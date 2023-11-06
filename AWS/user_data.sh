#!/bin/bash

# cli command to start instance
# aws ec2 run-instances --user-data file://user_data.txt --instance-type c5n.18xlarge --count 1 --image-id ami-08cba41c585e4a2e2 --region us-east-2 --key-name Processor --iam-instance-profile '{"Name":"Processor"}' --security-group-ids "sg-0fc864d44ef677a07" --profile jlaser_ciroh

echo "EXECUTING USER DATA"

cd /home/ec2-user

sudo dnf install git -y
python3 -m venv ./venv-datastream
git clone https://github.com/CIROH-UA/ngen-datastream.git
source ./venv-datastream/bin/activate && pip3 install --upgrade pip
pip3 install -r ./ngen-datastream/requirements.txt
deactivate

python3 -m venv ./venv-ngen-cal
git clone --branch realization_validation https://github.com/JordanLaserGit/ngen-cal.git
source ./venv-ngen-cal/bin/activate && pip3 install --upgrade pip
pip3 install -r ./ngen-cal/requirements.txt
pip3 install -e ./ngen-cal/python/ngen_conf
deactivate

# sudo dnf install go -y
# go install github.com/aaraney/ht@latest

touch /tmp/userdata_complete

echo "USERDATA COMPLETE"
