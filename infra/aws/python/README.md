# regenerate_missing
Finds NRDS simulations whose outputs are missing and relaunches them on the state machine ([#397](https://github.com/CIROH-UA/ngen-datastream/issues/397)). Run it from GitHub: **Actions → Regenerate Missing NRDS Data → Run workflow** on `main`, and fill in the range. It defaults to a dry run. Check the job summary, which lists every missing simulation, and the `regenerate-missing-<run id>` artifact, which holds each rendered execution and a `manifest.json`. Then run it again with **dry_run** unchecked to submit. Submitting is only allowed from `main`. A pull request that changes the tool runs the tests and a small dry run against the deployed schedules.

Or run it locally with AWS credentials:

```
pip install -e infra/aws/python
python -m research_datastream.regenerate_missing \
  --start 20260820 --end 20260823 \
  --datastreams cfe_nom,forcing --run-types short_range --init-cycles 23 \
  --out ./regenerate --dry-run
```

`--datastreams`, `--run-types`, `--init-cycles`, `--vpus` and `--members` take a comma-separated list or `all` (the default). A filter only narrows simulations that have that dimension, so the CONUS-wide `forcing` run is kept by `--vpus 01`. Leave a datastream out with `--datastreams`.

How it works:
1. The deployed EventBridge schedules (`--environment`, default `prod`) are the list of simulations. Each schedule's payload is the clean, rendered execution for one datastream, run type, init, member and VPU, with `DAILY` in place of the date.
2. For each date, a simulation is complete when the object the checker lambda looks for exists: `merkdir.file` for datastream runs, `metadata/forcings_metadata/metadata.csv` for forcing and restart runs.
3. A missing simulation's execution comes from the `execution.json` the commander lambda stored beside its outputs, with the failed run's state removed (`InstanceId`, `t0`, `retry_attempt`, ...). If none was stored, or with `--source schedule`, the schedule's payload is used instead. Every `DAILY` is set to the date, and `-s DAILY` gets `-e <date>0000` so datastreamcli simulates that day and not today. Shell that reads the instance clock to find the run date is pinned to the date too: `$(date -u +%Y%m%d)` becomes the date, `$(date -u -d yesterday +%Y%m%d)` the day before, and `$(date -u +%H)` becomes `23`. A simulation whose command reads the clock in any other way is skipped rather than sent with the wrong date.
4. Each execution is written to `--out/executions/` and, without `--dry-run`, started with `stepfunctions start-execution`.

It skips a simulation that:
- already has its outputs (the check in step 2), so only the holes in the requested range are sent;
- is less than `--min-age-hours` old (default 12), measured from its cycle time (date + init hour, UTC), so the schedules and their retries can still finish it;
- already has a regeneration running: a RUNNING execution on the state machine whose name, minus the trailing tag, matches (`regen_<datastream>_<run_type>_<date>_i<init>[_m<member>][_v<vpu>]`).

Inputs are not checked. If a run's forcing or restart is missing, the execution fails like any other run. qkrig is not regenerated.

`--max-executions` (default 500) refuses an oversized batch before anything is submitted.

# gen_vpu_execs
This script will generate all required execution files for the NextGen Research DataStream.

Run the script with:

```
cd infra/aws
python python/src/research_datastream/gen_vpu_execs.py \
--arch arm \
--inputs terraform/modules/schedules/config/execution_forecast_inputs.json \
--ami_file terraform/modules/schedules/config/community_ami.txt \
--exec_template_vpu terraform/modules/schedules/executions/templates/execution_datastream_VPU_template.json \
--exec_template_fp terraform/modules/schedules/executions/templates/execution_datastream_fp_template.json \
--out_dir terraform/modules/schedules/executions
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
    "runuser -l ec2-user -c '/home/ec2-user/ngen-datastream/scripts/datastream -s DAILY -n $NPROCS -F s3://ciroh-community-ngen-datastream/v2.2/ngen.DAILY/forcing_$RUN_TYPE_L/$INIT/ngen.t$INITz.$RUN_TYPE_L.forcing.$FCST.VPU_$VPU.nc --FORCING_SOURCE NWM_V3_$RUN_TYPE_H_$INIT_$MEMBER -d /home/ec2-user/outputs -r /home/ec2-user/resources/VPU_$VPU -R https://ciroh-community-ngen-datastream.s3.us-east-1.amazonaws.com/realizations/realization_VPU_$VPU.json --S3_BUCKET ciroh-community-ngen-datastream --S3_PREFIX v2.2/ngen.DAILY/$RUN_TYPE_L/$INIT/VPU_$VPU'"

],
"run_options":{
  "ii_terminate_instance" : true,
  "ii_delete_volume"      : true,
  "ii_check_s3"           : true,
  "timeout_s"             : 2400
},
"instance_parameters" :
{
  "ImageId"            : "",
  "InstanceType"       : "",
  "KeyName"            : "",
  "SecurityGroupIds"   : ["],
  "IamInstanceProfile": {
    "Name": ""
  },
  "TagSpecifications"   :[
    {
        "ResourceType": "instance",
        "Tags": [
            {
                "Key"   : "",
                "Value" : ""
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
