{
  "commands": [
    "echo --s3_bucket ${s3_bucket} --s3_prefix outputs/qkrig/qkrig.DAILY  # parser hint; streamcommander substitutes DAILY token to yesterday's UTC date (YYYYMMDD)",
    "runuser -l ec2-user -c 'mkdir -p /home/ec2-user/run/datastream-metadata /home/ec2-user/kv /home/ec2-user/exports /home/ec2-user/hydrofabric'",
    "runuser -l ec2-user -c 'rm -rf /home/ec2-user/hydrofabric/conus_nextgen.gpkg; { aws s3 cp s3://${s3_bucket}/resources/v2.2_hydrofabric/conus_nextgen.gpkg /home/ec2-user/hydrofabric/conus_nextgen.gpkg --no-progress; echo \"AWS_S3_CP_EXIT=$?\"; ls -la /home/ec2-user/hydrofabric/; file /home/ec2-user/hydrofabric/conus_nextgen.gpkg 2>&1 || true; } 2>&1 | tee /home/ec2-user/run/setup.log; aws s3 cp /home/ec2-user/run/setup.log s3://${s3_bucket}/outputs/qkrig/qkrig.DAILY/logs/setup.log --no-progress || true; test -s /home/ec2-user/hydrofabric/conus_nextgen.gpkg || { echo \"FATAL: gpkg missing/empty\"; exit 1; }'",
    "runuser -l ec2-user -c 'DATE=DAILY && DATE=$${DATE:0:4}-$${DATE:4:2}-$${DATE:6:2} && docker run --rm -e DATE=$${DATE} -e MAX_PROCS=4 -v /home/ec2-user/kv:/qkrig/usgs_hourly_retrieval_logs -v /home/ec2-user/exports:/qkrig/exports -v /home/ec2-user/hydrofabric/conus_nextgen.gpkg:/qkrig/hydrofabric/conus_nextgen.gpkg:ro -u $(id -u):$(id -g) awiciroh/qkrig:2.2.0 2>&1 | tee /home/ec2-user/run/docker.log'",
    "runuser -l ec2-user -c 'DATE=DAILY && DATE=$${DATE:0:4}-$${DATE:4:2}-$${DATE:6:2} && aws s3 cp /home/ec2-user/kv s3://${s3_bucket}/outputs/qkrig/cache/kv/ --recursive --exclude \"*\" --include \"$${DATE}_*.kv.txt\" --no-progress'",
    "runuser -l ec2-user -c 'DATE=DAILY && DATE=$${DATE:0:4}-$${DATE:4:2}-$${DATE:6:2} && rm -rf /tmp/staging && mkdir -p /tmp/staging && for h in 00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23; do if [ -e /home/ec2-user/exports/interp_$${DATE}_$${h}.nc ]; then mkdir -p /tmp/staging/$${h} && cp /home/ec2-user/exports/interp_$${DATE}_$${h}.nc /home/ec2-user/exports/variogram_$${DATE}_$${h}.csv /tmp/staging/$${h}/; fi; done && aws s3 sync /tmp/staging s3://${s3_bucket}/outputs/qkrig/qkrig.DAILY/ --no-progress'",
    "runuser -l ec2-user -c 'PARQUET=/home/ec2-user/exports/catchment_csv/qkrig_output_DAILY.parquet && [ -s \"$PARQUET\" ] && aws s3 cp \"$PARQUET\" s3://${s3_bucket}/outputs/qkrig/qkrig.DAILY/qkrig_output_DAILY.parquet --no-progress || true'",
    "runuser -l ec2-user -c '[ -s /home/ec2-user/run/docker.log ] && aws s3 cp /home/ec2-user/run/docker.log s3://${s3_bucket}/outputs/qkrig/qkrig.DAILY/logs/docker.log --no-progress || true'",
    "runuser -l ec2-user -c 'if [ -d /home/ec2-user/exports/plots ]; then aws s3 sync /home/ec2-user/exports/plots s3://${s3_bucket}/outputs/qkrig/qkrig.DAILY/plots/ --no-progress; fi'",
    "runuser -l ec2-user -c 'echo \"DATASTREAM_END: $(date -u +%Y%m%d%H%M%S)\" > /home/ec2-user/run/datastream-metadata/profile.txt'",
    "runuser -l ec2-user -c 'aws s3 cp /home/ec2-user/run/datastream-metadata/profile.txt s3://${s3_bucket}/outputs/qkrig/qkrig.DAILY/datastream-metadata/profile.txt --no-progress'"
  ],
  "run_options": {
    "ii_terminate_instance": true,
    "ii_delete_volume": true,
    "ii_check_s3": false,
    "ii_cheapo": false,
    "timeout_s": ${timeout_s},
    "n_retries_allowed": 0
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
          {"Key": "Name", "Value": "${environment_suffix}_qkrig_daily"},
          {"Key": "Project", "Value": "qkrig_daily_FULLCONUS"}
        ]
      },
      {
        "ResourceType": "volume",
        "Tags": [
          {"Key": "Name", "Value": "${environment_suffix}_qkrig_daily_vol"}
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
