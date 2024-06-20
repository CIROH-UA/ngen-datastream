# Forcing Processor
Forcingprocessor converts National Water Model (NWM) forcing data into Next Generation National Water Model (NextGen) forcing data. The motivation for this tool is NWM data is gridded and stored within netCDFs for each forecast hour. Ngen inputs this same forcing data, but in the format of per-catchment csv files that hold time series data. Forcingprocessor is driven by a configuration file that is explained, with an example, in detail below. The config argument accepts an s3 URL.

## Install
```
cd /ngen-datastream/forcingprocessor/ && pip install -e .
```

## Run the forcingprocessor
```
python ./src/forcingprocessor/processor.py ./configs/conf.json
```
Prior to executing the processor, the user will need to obtain a geopackage file to define the spatial domain. [hfsubset](https://github.com/lynker-spatial/hfsubsetCLI) will provide a geopackage which contains a necessary layer, `forcing-weights`, for `processor.py`. The user will define the time domain by generating the forcing filenames for `processor.py` via `nwm_filenames_generator.py`, which is explained [here](#nwm_file).

## Example `conf.json`
```
{
    "forcing"  : {
        "nwm_file"     : "",
        "gpkg_file"    : ""
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
| gpkg_file       | Geopackage file to define spatial domain. Use [hfsubset](https://github.com/lynker-spatial/hfsubsetCLI) to generate a geopackage with a `forcing-weights` layer. Accepts local absolute path, s3 URI or URL. |  :white_check_mark: |

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