{
  "commands": [
    "echo --s3_bucket ${s3_bucket} --s3_prefix outputs/nwm_routing/v2.2_hydrofabric/ngen.DAILY/short_range/${init}/VPU_${vpu} --forcing_source NWM_V3_CHRTOUT_SHORT_RANGE_${init}  # parser hint: streamcommander reads bucket/prefix/forcing_source from here; forcing_source sets the init-hour date cutoff, and every occurrence of the full prefix string in these commands gets its date token replaced with the run date",
    "runuser -l ec2-user -c 'rm -rf /home/ec2-user/t-route /home/ec2-user/upload /home/ec2-user/run && mkdir -p /home/ec2-user/t-route /home/ec2-user/run'",
    "runuser -l ec2-user -c 'set -o pipefail && PREFIX=outputs/nwm_routing/v2.2_hydrofabric/ngen.DAILY/short_range/${init}/VPU_${vpu} && DATE=$(echo $PREFIX | grep -oE \"[0-9]{8}\" | head -1) && docker run --rm -v /home/ec2-user/t-route:/routing-comparison-nwm-nextgen-troute/t-route -e START_TIME=$${DATE}${init}00 -e FORECAST_TYPE=1 -e VPU=${vpu} -e N_CPUS=${nprocs} ${preprocess_image} 2>&1 | tee /home/ec2-user/run/preprocess.log'",
    "runuser -l ec2-user -c '[ -e /home/ec2-user/t-route/troute.yaml ] && [ -e /home/ec2-user/t-route/restart/troute_restart.nc ] || { echo FATAL: preprocess did not produce troute.yaml or restart; exit 1; }'",
    "runuser -l ec2-user -c 'set -o pipefail && docker run --rm -v /home/ec2-user/t-route:/ngen/ngen/data:rw -w /ngen/ngen/data --entrypoint python ${routing_image} -m nwm_routing -f -V4 ./troute.yaml 2>&1 | tee /home/ec2-user/run/troute.log'",
    "runuser -l ec2-user -c 'set -o pipefail && docker run --rm -v /home/ec2-user/t-route:/routing-comparison-nwm-nextgen-troute/t-route ${postprocess_image} 2>&1 | tee /home/ec2-user/run/postprocess.log'",
    "runuser -l ec2-user -c 'P=$(ls /home/ec2-user/t-route/outputs/troute/converted_*.parquet 2>/dev/null | head -1); [ -n \"$P\" ] && [ $(stat -c%s \"$P\") -gt 100000 ] || { echo FATAL: converted parquet missing or too small; exit 1; }'",
    "runuser -l ec2-user -c 'mkdir -p /home/ec2-user/upload/ngen-run/outputs/troute /home/ec2-user/upload/datastream-metadata && cp /home/ec2-user/t-route/outputs/troute/converted_*.parquet /home/ec2-user/upload/ngen-run/outputs/troute/ && cp /home/ec2-user/t-route/outputs/troute/troute_output_*.nc /home/ec2-user/upload/ngen-run/outputs/troute/ && cp /home/ec2-user/run/*.log /home/ec2-user/upload/datastream-metadata/ && echo \"DATASTREAM_END: $(date -u +%Y%m%d%H%M%S)\" > /home/ec2-user/upload/datastream-metadata/profile.txt'",
    "runuser -l ec2-user -c 'docker run --rm -v /home/ec2-user/upload:/mounted_dir -u $(id -u):$(id -g) zwills/merkdir /merkdir/merkdir gen -o /mounted_dir/merkdir.file /mounted_dir'",
    "runuser -l ec2-user -c 'PREFIX=outputs/nwm_routing/v2.2_hydrofabric/ngen.DAILY/short_range/${init}/VPU_${vpu} && aws s3 sync /home/ec2-user/upload s3://${s3_bucket}/$PREFIX/ --no-progress'"
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
            "Value": "${environment_suffix}_nwm_routing_short_range_VPU${vpu}_init${init}"
          },
          {
            "Key": "Project",
            "Value": "nwm_routing_short_range_VPU_${vpu}"
          }
        ]
      },
      {
        "ResourceType": "volume",
        "Tags": [
          {
            "Key": "Name",
            "Value": "${environment_suffix}_nwm_routing_short_range_VPU${vpu}_init${init}_vol"
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
