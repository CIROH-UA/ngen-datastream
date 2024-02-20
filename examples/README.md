# Examples
Below are a few different ways to run the datastream. Note that the `"DAILY"` runs are large and intended for HPC.

## Small Run
This run will include forcings from 200301200100 to 200301210100. The s3 URI will be sync'd into `RESOURCE_PATH`. The geopackage in the `RESOURCE_PATH` represents the smallest VPU (09) and defines the spatial domain of the datastream run.

`/ngen-datastream/configs/conf_datastream_small.sh`
```
START_DATE="200301200100"
END_DATE="200301210100"
DATA_PATH="/home/ec2-user/datastream-small-run"
RESOURCE_PATH="s3://ngen-datastream/resources_small/"
# RELATIVE_TO=""
# S3_MOUNT=""
# SUBSET_ID_TYPE=""
# SUBSET_ID=""
# HYDROFABRIC_VERSION=""
```

`RESOURCE_PATH`
```
RESOURCE_PATH/
│
├── nextgen_09.gpkg 
|
├── nwm_example_grid_file.nc 
|
├── conf_nwmurl.json
│
├── ngen-configs
    │
    ├── config.ini
    │
    ├── ngen.yaml    
    │
    ├── realization.json    
```
`conf_nwmurl.json`
```
{
    "forcing_type" : "retrospective",
    "start_date"   : "",
    "end_date"     : "",
    "urlbaseinput" : 1,
    "selected_object_type" : [1],
    "selected_var_types"   : [6],
    "write_to_file" : true
}
```
Note that `start_date` and `end_date` are not set. The datastream will do this for you.

Run it: `./ngen-datastream/scripts/stream.sh --CONF-FILE ./ngen-datastream/configs/conf_datastream_small.sh`

## "DAILY"
For a CONUS wide run on today's date:
```
START_DATE="DAILY",
END_DATE= 
DATA_PATH="/home/ec2-user/example-datastream-folder"
RESOURCE_PATH="s3://ngen-datastream/resources_default/"
# RELATIVE_TO=""
# S3_MOUNT=""
# SUBSET_ID_TYPE=""
# SUBSET_ID=""
# HYDROFABRIC_VERSION=""
```

`RESOURCE_PATH`
```
RESOURCE_PATH/
│
├── conus.gpkg 
|
├── nwm_example_grid_file.nc 
|
├── weights.json
│
├── ngen-configs
    │
    ├── config.ini
    │
    ├── ngen.yaml    
    │
    ├── realization.json    
```

no `conf_nwmurl.json` needed
