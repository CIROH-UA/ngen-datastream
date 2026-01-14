{
  "commands": [
    "runuser -l ec2-user -c 'export SKIP_VALIDATION=True FP_TAG=1.0.3 DS_TAG=1.0.2 NGIAB_TAG=1.5.0 && /home/ec2-user/ngen-datastream/scripts/datastream -s DAILY -n ${nprocs} -F s3://ciroh-community-ngen-datastream/v2.2/ngen.DAILY/forcing_${run_type_l}/${init}/ngen.t${init}z.${run_type_l}.forcing.${fcst}.VPU_${vpu}.nc --FORCING_SOURCE NWM_V3_${run_type_h}_${init}${member_suffix} -d /home/ec2-user/outputs -r s3://ciroh-community-ngen-datastream/v2.2_resources/VPU_${vpu} -R https://ciroh-community-ngen-datastream.s3.amazonaws.com/realizations/realization_VPU_${vpu}.json --S3_BUCKET ciroh-community-ngen-datastream --S3_PREFIX v2.2/ngen.DAILY/${run_type_l}/${init}${member_path}/VPU_${vpu}'"
  ],
  "run_options": {
    "ii_terminate_instance": true,
    "ii_delete_volume": true,
    "ii_check_s3": true,
    "ii_cheapo": true,
    "timeout_s": 3600,
    "n_retries_allowed": 2
  },
  "instance_parameters": {
    "ImageId": "${ami_id}",
    "InstanceType": "${instance_type}",
    "KeyName": "${key_name}",
    "SecurityGroupIds": ${security_group_ids},
    "IamInstanceProfile": {
      "Name": "${instance_profile}"
    },
    "TagSpecifications": [
      {
        "ResourceType": "instance",
        "Tags": [
          {
            "Key": "Project",
            "Value": "datastream_FULLCONUS_v1.2_${run_type_l}_${vpu}"
          }
        ]
      }
    ],
    "BlockDeviceMappings": [
      {
        "DeviceName": "/dev/xvda",
        "Ebs": {
          "VolumeSize": ${volume_size},
          "VolumeType": "gp3"
        }
      }
    ]
  }
}
