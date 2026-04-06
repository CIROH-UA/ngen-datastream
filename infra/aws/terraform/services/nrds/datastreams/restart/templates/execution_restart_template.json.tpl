{
  "commands": [
    "runuser -l ec2-user -c 'mkdir -p /home/ec2-user/run/datastream-metadata'",
    "runuser -l ec2-user -c 'mkdir -p /home/ec2-user/run/ngen-run/config'",
    "runuser -l ec2-user -c 'cp /home/ec2-user/datastreamcli/configs/ngen/realization_sloth_nom_cfe_pet.json /home/ec2-user/run'",
    "runuser -l ec2-user -c 'docker run --rm -v /home/ec2-user/run:/mounted_dir -u $(id -u):$(id -g) -w /mounted_dir/datastream-metadata awiciroh/datastream:${ds_tag} python3 /datastreamcli/src/datastreamcli/configure_datastream.py --docker_mount /mounted_dir --start_date DAILY --end_date DAILY --data_dir /home/ec2-user/run --forcing_source NWM_V3_ANALYSIS_ASSIM_RESTART_CHRT_${init} --hydrofabric_version v2.2 --realization /mounted_dir/realization_sloth_nom_cfe_pet.json --realization_provided /home/ec2-user/run/realization_sloth_nom_cfe_pet.json --s3_bucket ${s3_bucket} --s3_prefix restarts/v2.2_hydrofabric/ngen.DAILY/${init}'",
    "runuser -l ec2-user -c 'docker run --rm -v /home/ec2-user/run:/mounted_dir -u $(id -u):$(id -g) -w /mounted_dir/datastream-metadata awiciroh/forcingprocessor:${fp_tag} python3 /forcingprocessor/src/forcingprocessor/nwm_filenames_generator.py /mounted_dir/datastream-metadata/conf_nwmurl.json'",
    "runuser -l ec2-user -c 'mv /home/ec2-user/run/filenamelist.txt /home/ec2-user/run/datastream-metadata/'",
    "runuser -l ec2-user -c 'docker run --rm -e AWS_ACCESS_KEY_ID=$(echo $AWS_ACCESS_KEY_ID) -e AWS_SECRET_ACCESS_KEY=$(echo $AWS_SECRET_ACCESS_KEY) -v /home/ec2-user/run:/mounted_dir -u $(id -u):$(id -g) -w /mounted_dir/datastream-metadata awiciroh/forcingprocessor:${fp_tag} python3 /forcingprocessor/src/forcingprocessor/processor.py /mounted_dir/datastream-metadata/conf_fp.json'"
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
            "Value": "${environment_suffix}_restart_init${init}"
          },
          {
            "Key": "Project",
            "Value": "restart_generation"
          }
        ]
      },
      {
        "ResourceType": "volume",
        "Tags": [
          {
            "Key": "Name",
            "Value": "${environment_suffix}_restart_init${init}_vol"
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
