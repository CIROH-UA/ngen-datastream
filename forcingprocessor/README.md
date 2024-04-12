# Forcing Processor
Forcingprocessor converts National Water Model (NWM) forcing data into Next Generation National Water Model (NextGen) forcing data. The motivation for this tool is NWM data is gridded and stored within netCDFs for each forecast hour. Ngen inputs this same forcing data, but in the format of per-catchment csv files that hold time series data. Forcingprocessor is driven by a configuration file that is explained, with an example, in detail below. The config argument accepts an s3 URL.

## Install
```
pip install -e /ngen-datastream/forcingprocessor
```

## Run the forcingprocessor
```
python forcingprocessor.py conf.json
```
See the docker README for example run commands from the container.

## Example `conf.json`
```
{
    "forcing"  : {
        "nwm_file"     : "",
        "weight_file"  : ""
    },

    "storage":{
        "output_path"      : "",
        "output_file_type" : []
    },    

    "run" : {
        "verbose"       : true,
        "collect_stats" : true,
        "nprocs"        : 2
    }
}
```

## `conf.json` Options 
### 1. Forcing
| Field             | Description              | Required |
|-------------------|--------------------------|----------|
| nwm_file          | Path to a text file containing nwm file names. One filename per line. [Tool](#nwm_file) to create this file | :white_check_mark: |
| weight_file       | Weight file for the run Accepts local absolute path, s3 URI or URL. [Tool](#weight_file) to create this file |  :white_check_mark: |

### 2. Storage

| Field             | Description                       | Required |
|-------------------|-----------------------------------|----------|
| storage_type      | Type of storage (local or s3)     | :white_check_mark: |
| output_path       | Path to write data to. Accepts local path or s3 | :white_check_mark: |
| output_file_type  | List of output file types, e.g. ["tar","parquet"]  | :white_check_mark: |

### 3. Run
| Field             | Description                    | Required |
|-------------------|--------------------------------|----------|
| verbose           | Get print statements, defaults to false           |  :white_check_mark: |
| collect_stats     | Collect forcing metadata, defaults to true       |  :white_check_mark: |
| nprocs      | Number of data processing processes, defaults to 50% available cores |   |
| nfile_chunk       | Number of files to process each write, defaults to 1000000. Only set this if experiencing memory constraints due to large number of nwm forcing files |   |

## nwm_file
A text file given to forcingprocessor that contains each nwm forcing file name. These can be URLs or local paths. This file can be generated with the [nwmurl tool](https://github.com/CIROH-UA/nwmurl) and a [generator script](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor/nwm_filenames_generator.py) has been provided within this repo. The config argument accepts an s3 URL. 
 ```
 python nwm_filenames_generator.py conf_nwm_files.json
 ```
 An example configuration file:
 ```
 {
    "forcing_type" : "operational_archive",
    "start_date"   : "202310300000",
    "end_date"     : "202310300000",
    "runinput"     : 1,
    "varinput"     : 5,
    "geoinput"     : 1,
    "meminput"     : 0,
    "urlbaseinput" : 7,
    "fcst_cycle"   : [0],
    "lead_time"    : [1]
}
 ```

## weight_file
In order to retrieve forcing data from a NWM grid for a given catchment, the indices (weights) of that catchment must be provided to the forcingprocessor in the weights file. The script will ingest every set of catchment weights and produce a corresponding forcings file. These weights can be generated manually from a [geopackage](https://lynker-spatial.s3.amazonaws.com/v20.1/gpkg/nextgen_01.gpkg) with the [weight generator](https://github.com/CIROH-UA/ngen-datastream/blob/main/forcingprocessor/src/forcingprocessor/weights_parq2json.py). An example weight file has been provided [here](https://ngen-datastream.s3.us-east-2.amazonaws.com/resources_default/weights_w_cov.json). 

 ```
 python weights_parq2json.py --gpkg <path to geopackage> --outname <path to output weights to> --version <hydrofabric version>
 ```