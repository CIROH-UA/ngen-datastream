# gen_vpu_execs
This script will generate all required execution files for the NextGen Research DataStream.

Run the script with:

```
cd research_datastream
python python/src/research_datastream/gen_vpu_execs.py \
--arch arm \
--inputs infra/aws/terraform/modules/schedules/config/execution_forecast_inputs.json \
--ami_file infra/aws/terraform/modules/schedules/config/community_ami.txt \
--exec_template_vpu infra/aws/terraform/modules/schedules/executions/templates/execution_datastream_VPU_template.json \
--exec_template_fp infra/aws/terraform/modules/schedules/executions/templates/execution_datastream_fp_template.json \
--out_dir infra/aws/terraform/modules/schedules/executions
```

Where the platform architecture is set by `--arch`. Choices are arm or x86

The `--inputs` options provides the forecast inputs file which takes the form below. See the [file in this repository](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/modules/schedules/config/execution_forecast_inputs.json) for a completed file.
```
{
  "short_range": {
    "init_cycles": [],
    "instance_types": {},
    "volume_size": 
  },
  "medium_range": {
    "init_cycles": [],
    "ensemble_members": [],
    "instance_types": {},
    "volume_size": 
  },
  "analysis_assim_extend": {
    "init_cycles": [],
    "instance_types": {},
    "volume_size": 
  }
}

```

`--ami_file` sets the file responsible for holding the AWS AMI of each platform architecture. The file takes the following form.
```
x86: ami-12345678901234567
arm: ami-12345678901234567
```

`--exec_template_vpu`sets the template file for all NextGen executions distributed by VPU based spatial domains. This file takes the following form
```
{  
  "commands"  : [
    "runuser -l ec2-user -c 'export SKIP_VALIDATION=True FP_TAG=1.0.3 DS_TAG=1.0.2 NGIAB_TAG=1.5.0 && /home/ec2-user/ngen-datastream/scripts/datastream -s DAILY -n $NPROCS -F s3://ciroh-community-ngen-datastream/v2.2/ngen.DAILY/forcing_$RUN_TYPE_L/$INIT/ngen.t$INITz.$RUN_TYPE_L.forcing.$FCST.VPU_$VPU.nc --FORCING_SOURCE NWM_V3_$RUN_TYPE_H_$INIT_$MEMBER -d /home/ec2-user/outputs -r s3://ciroh-community-ngen-datastream/v2.2_resources/VPU_$VPU -R https://ciroh-community-ngen-datastream.s3.amazonaws.com/realizations/realization_VPU_$VPU.json --S3_BUCKET ciroh-community-ngen-datastream --S3_PREFIX v2.2/ngen.DAILY/$RUN_TYPE_L/$INIT/$MEMBER/VPU_$VPU'"
],
"run_options":{
        "ii_terminate_instance": true,
        "ii_delete_volume": true,
        "ii_check_s3": true,
        "ii_cheapo" :true,
        "timeout_s": 3600,
        "n_retries_allowed": 2
},
"instance_parameters" :
{
  "ImageId"            : "ami-0ef008a1e6d9aa12d",
  "InstanceType"       : "m8g.xlarge",
  "KeyName"            : "jlaser_community_east1",
  "SecurityGroupIds"   : ["sg-0fcbe0c6d6faa0117"],
  "IamInstanceProfile": {
    "Name": "datastream_community_ec2_profile"
  },
  "TagSpecifications"   :[
    {
        "ResourceType": "instance",
        "Tags": [
            {
                "Key"   : "Project",
                "Value" : "datastream_FULLCONUS_v1.2_$RUN_TYPE_L_$VPU"
            }          
        ]
    }
],
  "BlockDeviceMappings":[
    {
        "DeviceName": "/dev/xvda",  
        "Ebs": {
            "VolumeSize": 32,
            "VolumeType": "gp3"  
        }
    }
  ]
}
}
```
Note that the script will only embed values for the terms of the form `$VARIABLE`. So fields like `SecurityGroupIds` and `IamInstanceProfile` must be written into the template file manually before executing `gen_vpu_execs.py`. To see examples, see the output execution files found in any [NextGen Research DataStream](https://datastream.ciroh.org/index.html) metadata.


`--exec_template_fp` sets the execution file tempalte for forcing processing. It looks identical to the file above, with the exception of the differing commands:
```
    "runuser -l ec2-user -c 'mkdir -p /home/ec2-user/run/datastream-metadata'",
    "runuser -l ec2-user -c 'mkdir -p /home/ec2-user/run/ngen-run/config'",
    "runuser -l ec2-user -c 'cp /home/ec2-user/ngen-datastream/configs/ngen/realization_sloth_nom_cfe_pet.json /home/ec2-user/run'",
    "runuser -l ec2-user -c 'docker run --rm -v /home/ec2-user/run:/mounted_dir -u $(id -u):$(id -g) -w /mounted_dir/datastream-metadata awiciroh/datastream:latest python3 /ngen-datastream/python_tools/src/python_tools/configure_datastream.py --docker_mount /mounted_dir --start_date DAILY --data_path /home/ec2-user/run --forcing_source NWM_V3_$RUN_TYPE_H_$INIT_$MEMBER --forcing_split_vpu 01,02,03W,03N,03S,04,05,06,07,08,09,10L,10U,11,12,13,14,15,16,17,18 --hydrofabric_version v2.2 --realization_file /mounted_dir/realization_sloth_nom_cfe_pet.json --s3_bucket ciroh-community-ngen-datastream --s3_prefix v2.2/ngen.DAILY/forcing_$RUN_TYPE_L/$INIT'",
    "runuser -l ec2-user -c 'docker run --rm -v /home/ec2-user/run:/mounted_dir -u $(id -u):$(id -g) -w /mounted_dir/datastream-metadata awiciroh/forcingprocessor:latest python3 /ngen-datastream/forcingprocessor/src/forcingprocessor/nwm_filenames_generator.py /mounted_dir/datastream-metadata/conf_nwmurl.json'",
    "runuser -l ec2-user -c 'cp /home/ec2-user/hydrofabric/v2.2/nextgen_*_weights.json /home/ec2-user/run'",
    "runuser -l ec2-user -c 'docker run --rm -e AWS_ACCESS_KEY_ID=$(echo $AWS_ACCESS_KEY_ID) -e AWS_SECRET_ACCESS_KEY=$(echo $AWS_SECRET_ACCESS_KEY) -v /home/ec2-user/run:/mounted_dir -u $(id -u):$(id -g) -w /mounted_dir/datastream-metadata awiciroh/forcingprocessor:latest python3 /ngen-datastream/forcingprocessor/src/forcingprocessor/processor.py /mounted_dir/datastream-metadata/conf_fp.json'"
```

Finally, `--out_dir` sets the output directory.
