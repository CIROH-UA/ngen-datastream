{
  "commands": [
    "runuser -l ec2-user -c 'export SKIP_VALIDATION=True DS_TAG=latest-arm NGIAB_TAG=v1.6.0 && /home/ec2-user/datastreamcli/scripts/datastream -s DAILY -n ${nprocs} -F s3://ciroh-community-ngen-datastream/v2.2/ngen.DAILY/forcing_${run_type_l}/${init}/ngen.t${init}z.${run_type_l}.forcing.${fcst}.VPU_${vpu}.nc --FORCING_SOURCE NWM_V3_${run_type_h}_${init}${member_suffix} -d /home/ec2-user/outputs -g s3://ciroh-community-ngen-datastream/v2.2_resources/VPU_${vpu}/config/nextgen_VPU_${vpu}.gpkg -R https://ciroh-community-ngen-datastream.s3.amazonaws.com/realizations/realization_rust_lstm_troute.json --S3_BUCKET ciroh-community-ngen-datastream --S3_PREFIX outputs/lstm/v2.2_hydrofabric/ngen.DAILY/${run_type_l}/${init}${member_path}/VPU_${vpu}'"
  ],
  "run_options": {
    "ii_terminate_instance": true,
    "ii_delete_volume": true,
    "ii_check_s3": true,
    "ii_cheapo": true,
    "timeout_s": ${timeout_s},
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
            "Key": "Name",
            "Value": "${environment_suffix}_LSTM_${run_type_l}_VPU${vpu}_init${init}${member_suffix}"
          },
          {
            "Key": "Project",
            "Value": "datastream_LSTM_v1.0_${run_type_l}_${vpu}"
          }
        ]
      },
      {
        "ResourceType": "volume",
        "Tags": [
          {
            "Key": "Name",
            "Value": "${environment_suffix}_LSTM_${run_type_l}_VPU${vpu}_init${init}${member_suffix}_vol"
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
