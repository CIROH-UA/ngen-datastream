{
  "commands": [
    "su - ec2-user -c 'rm -rf /home/ec2-user/outputs && export SKIP_VALIDATION=True DS_TAG=1.7.0 NGIAB_TAG=v1.7.0 && /home/ec2-user/datastreamcli/scripts/datastream -s DAILY -n ${nprocs} --FORCING_SOURCE NWM_V3_CHRTOUT_${run_type_h}_${init} -d /home/ec2-user/outputs -g s3://${s3_bucket}/resources/v2.2_hydrofabric/geopackages/VPU_${vpu}/nextgen_VPU_${vpu}.gpkg -R https://${s3_bucket}.s3.amazonaws.com/realizations/routing_only/realization_sloth_troute.json -t run/ngen-run/restart/channel_restart.nc -w s3://${s3_bucket}/resources/v2.2_hydrofabric/troute_restart/crosswalk.nc --S3_BUCKET ${s3_bucket} --S3_PREFIX outputs/routing_only/v2.2_hydrofabric/ngen.DAILY/${run_type_l}/${init}/VPU_${vpu}'"
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
    "IamInstanceProfile": {
      "Name": "${instance_profile}"
    },
    "TagSpecifications": [
      {
        "ResourceType": "instance",
        "Tags": [
          {
            "Key": "Name",
            "Value": "${environment_suffix}_routing_only_${run_type_l}_VPU${vpu}_init${init}"
          },
          {
            "Key": "Project",
            "Value": "routing_only_${run_type_l}_VPU_${vpu}"
          }
        ]
      },
      {
        "ResourceType": "volume",
        "Tags": [
          {
            "Key": "Name",
            "Value": "${environment_suffix}_routing_only_${run_type_l}_VPU${vpu}_init${init}_vol"
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
