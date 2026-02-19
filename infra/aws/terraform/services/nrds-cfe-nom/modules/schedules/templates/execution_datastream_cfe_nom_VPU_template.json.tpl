{
  "commands": [
    "runuser -l ec2-user -c 'export SKIP_VALIDATION=True DS_TAG=1.4.0 NGIAB_TAG=v1.7.0 && /home/ec2-user/datastreamcli/scripts/datastream -s DAILY -n ${nprocs} -F s3://${s3_bucket}/forcings/v2.2_hydrofabric/ngen.DAILY/forcing_${run_type_l}/${init}/ngen.t${init}z.${run_type_l}.forcing.${fcst}.VPU_${vpu}.nc --FORCING_SOURCE NWM_V3_${run_type_h}_${init}${member_suffix} -d /home/ec2-user/outputs -N s3://${s3_bucket}/resources/v2.2_hydrofabric/bmi_configs/cfe_nom_fixed/VPU_${vpu}/config/ngen-bmi-configs.tar.gz -g s3://${s3_bucket}/resources/v2.2_hydrofabric/geopackages/VPU_${vpu}/nextgen_VPU_${vpu}.gpkg -R https://${s3_bucket}.s3.amazonaws.com/realizations/cfe_nom/realization_VPU_${vpu}.json --S3_BUCKET ${s3_bucket} --S3_PREFIX outputs/cfe_nom/v2.2_hydrofabric/ngen.DAILY/test/${run_type_l}/${init}${member_path}/VPU_${vpu}'"
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
            "Value": "${environment_suffix}_CFE_NOM_${run_type_l}_VPU${vpu}_init${init}${member_suffix}"
          },
          {
            "Key": "Project",
            "Value": "datastream_FULLCONUS_v1.2_${run_type_l}_${vpu}"
          }
        ]
      },
      {
        "ResourceType": "volume",
        "Tags": [
          {
            "Key": "Name",
            "Value": "${environment_suffix}_CFE_NOM_${run_type_l}_VPU${vpu}_init${init}${member_suffix}_vol"
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
