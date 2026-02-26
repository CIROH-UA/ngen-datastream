{
  "commands": [
    "runuser -l ec2-user -c 'mkdir -p /home/ec2-user/run/datastream-metadata'",
    "runuser -l ec2-user -c 'mkdir -p /home/ec2-user/run/ngen-run/config'",
    "runuser -l ec2-user -c 'cp /home/ec2-user/ngen-datastream/configs/ngen/realization_sloth_nom_cfe_pet.json /home/ec2-user/run'",
    "runuser -l ec2-user -c 'docker run --rm -v /home/ec2-user/run:/mounted_dir -u $(id -u):$(id -g) -w /mounted_dir/datastream-metadata awiciroh/datastream:1.0.2 python3 /ngen-datastream/python_tools/src/python_tools/configure_datastream.py --docker_mount /mounted_dir --start_date DAILY --data_dir /home/ec2-user/run --forcing_source NWM_V3_${run_type_h}_${init}${member_suffix} --forcing_split_vpu ${vpu_list} --hydrofabric_version v2.2 --realization /mounted_dir/realization_sloth_nom_cfe_pet.json --realization_provided /home/ec2-user/run/realization_sloth_nom_cfe_pet.json --s3_bucket ${s3_bucket} --s3_prefix forcings/v2.2_hydrofabric/ngen.DAILY/forcing_${run_type_l}/${init}'",
    "runuser -l ec2-user -c 'docker run --rm -v /home/ec2-user/run:/mounted_dir -u $(id -u):$(id -g) -w /mounted_dir/datastream-metadata awiciroh/forcingprocessor:1.0.3 python3 /ngen-datastream/forcingprocessor/src/forcingprocessor/nwm_filenames_generator.py /mounted_dir/datastream-metadata/conf_nwmurl.json'",
    "runuser -l ec2-user -c 'cp /home/ec2-user/hydrofabric/v2.2/nextgen_*_weights.json /home/ec2-user/run'",
    "runuser -l ec2-user -c 'docker run --rm -e AWS_ACCESS_KEY_ID=$(echo $AWS_ACCESS_KEY_ID) -e AWS_SECRET_ACCESS_KEY=$(echo $AWS_SECRET_ACCESS_KEY) -v /home/ec2-user/run:/mounted_dir -u $(id -u):$(id -g) -w /mounted_dir/datastream-metadata awiciroh/forcingprocessor:1.0.3 python3 /ngen-datastream/forcingprocessor/src/forcingprocessor/processor.py /mounted_dir/datastream-metadata/conf_fp.json'",
    "runuser -l ec2-user -c 'aws s3 cp /home/ec2-user/run/datastream-metadata/conf_nwmurl.json $(cat /home/ec2-user/run/datastream-metadata/conf_fp.json | jq -r '.storage.output_path')/metadata/forcings_metadata/conf_nwmurl.json --no-progress'"
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
    "IamInstanceProfile": {
      "Name": "${instance_profile}"
    },
    "TagSpecifications": [
      {
        "ResourceType": "instance",
        "Tags": [
          {
            "Key": "Name",
            "Value": "${environment_suffix}_CFE_NOM_${run_type_l}_fp_init${init}${member_suffix}"
          },
          {
            "Key": "Project",
            "Value": "datastream_FULLCONUS_v1.2_${run_type_l}_fp"
          }
        ]
      },
      {
        "ResourceType": "volume",
        "Tags": [
          {
            "Key": "Name",
            "Value": "${environment_suffix}_CFE_NOM_${run_type_l}_fp_init${init}${member_suffix}_vol"
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
