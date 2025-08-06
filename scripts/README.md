# scripts/datastream_guide
Run the guide script with
```
/scripts/datastream_guide
```
and an interactive program will run that will guide the user step-by-step to build a DataStreamCLI command. Each option is explained and there is an optional tour of the repository.

# scripts/datastream
This script is what is referred to as by DataStreamCLI. There are numerous ways to execute this script. See the [DataStreamCLI options docs](https://github.com/CIROH-UA/ngen-datastream/blob/main/docs/DATASTREAM_OPTIONS.md) for explainations of each cli arg. Some examples are provided below.

### One-off execution examples
1.
    For a NOM, CFE, PET, troute NextGen execution over VPU09 on 20200620 using the National Water Model v3 retrospective forcings:
    ```
    ./scripts/datastream -s 202006200100 \
                        -e 202006210000 \
                        -C NWM_RETRO_V3 \
                        -d ./data/datastream_test_1 \
                        -g https://ciroh-community-ngen-datastream.s3.us-east-1.amazonaws.com/v2.2_resources/VPU_09/config/nextgen_VPU_09.gpkg \
                        -R ./configs/ngen/realization_sloth_nom_cfe_pet_troute.json \
                        -n 4
    ```
    `-s` and `-e` set the start and end data. `-C` set the forcing source. `-d` sets the local output directory. `-g` sets the geopackage, which defines the spatial domain. `-R` sets the NextGen configuration file, also referred to as a realization file. `-n` sets the maximum number of processes to utilize during the DataStreamCLI execution.

2.
    For a simulation with the same NextGen configuration, but over a different time period, we can reuse the resource directory from the prior execution to take advantage of cached spatially dependent files.

    First, delete the cached time dependent forcings

    ```
    rm -rf ./data/datastream_test_1/datastream-resources/ngen-forcings
    ```

    Then execute using the resource directory and a different time period

    ```
    ./scripts/datastream -s 202006250100 \
                        -e 202006260000 \
                        -C NWM_RETRO_V3 \
                        -d ./data/datastream_test_2 \
                        -r ./data/datastream_test_1/datastream-resources \
                        -n 4
    ```    

### NextGen Research DataStream releated examples:
The backend software of the NextGen Research DataStream is DataStreamCLI. Several examples are given below to help illustrate the different ways DataStreamCLI can be executed. While the NextGen Research DataStream executions occur within AWS cloud, these commands will execute in a local environment. See the [NextGen Research DataStream docs](https://github.com/CIROH-UA/ngen-datastream/tree/main/research_datastream) for more information on the design.

Daily short range for VPU 16 forecast cycle 12 on 20250730. 
```
/ngen-datastream/scripts/datastream \
    -s DAILY \
    -e 202507300000 \
    -n 3 \
    -F s3://ciroh-community-ngen-datastream/v2.2/ngen.20250730/forcing_short_range/12/ngen.t12z.short_range.forcing.f001_f018.VPU_16.nc \
    -d /home/ec2-user/outputs \
    -r s3://ciroh-community-ngen-datastream.s3.us-east-1.amazonaws.com/v2.2_resources/VPU_16 \
    -R https://ciroh-community-ngen-datastream.s3.us-east-1.amazonaws.com/realizations/realization_VPU_16.json \
    --FORCING_SOURCE NWM_V3_SHORT_RANGE_12 \
    --S3_BUCKET ciroh-community-ngen-datastream \
    --S3_PREFIX test/v2.2/ngen.20250730/short_range/12/VPU_16
```

Note the `-e` options sets the date . This is required whenever the user desires a "DAILY" run using forcing from a day other than today. Therefore, the production research datastream system does not actually set the `-e` option.

Additionally, the NextGen Research DataStream executions riot set the following environment variables
```
export DS_TAG=1.0.1 NGIAB_TAG=v0.0.0
```
in order to override the default tag of "latest". 

# scripts/docker_builds.sh
This script handles the docker builds for the parent `datastream-deps` and the primary `datastream` and `forcingprocessor` docker containers. The script will build from the files locally, so it is easy for users to build their own variant containers and tag them readily. 

For example.
```
scripts/docker_builds.sh -e -d -f -t my-local-containers-latest
```

will build these containers locally

```
awiciroh/datastream-deps:my-local-containers-latest
awiciroh/datastream:my-local-containers-latest
awiciroh/forcingprocessor:my-local-containers-latest
```

Options
```
-e builds datastream-deps
-d builds datastream
-f builds forcingprocessor
-p pushes containers to dockerhub (for admin use only)
-t sets the tag
```
