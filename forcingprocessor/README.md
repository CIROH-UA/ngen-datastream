# Forcing Processor

Forcingprocessor converts National Water Model (NWM) forcing data into Next Generation National Water Model (ngen) forcing data. The motivation for this tool is NWM data is gridded and stored within netCDFs for each forecast hour. Ngen inputs this same forcing data, but in the format of per-catchment csv files that hold time series data. Forcingprocessor is driven by a configuration file that is explained, with an example, in detail below.

## Runing the forcingprocessor
```
python nwmforcing2ngen.py conf.json
```

## Run Notes
This tool is CPU, memory, and I/O intensive. For the best performance, run with `proc_threads` equal to than half of available cores and `write_threads` equal to the number of available cores. Best to experiment with your resources to find out what works best.


## nwm_file
A text file given to forcingprocessor that contains each nwm forcing file name. These can be URLs or local paths. This file can be generated with the [nwmurl tool](https://github.com/CIROH-UA/nwmurl) and a [generator script](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor/nwm_filenames_generator.py) that has been provided within this repo. 

## weight_file
In order to retrieve forcing data from a NWM grid for a given catchment, the indices (weights) of that catchment must be provided to the forcingprocessor in the weights file. The script will ingest every set of catchment weights and produce a corresponding forcings file. These weights can be generated manually from a geopackage https://noaa-owp.github.io/hydrofabric/articles/data_access.html with the [weight generator](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor/weight_generator.py). Also, tools are available to help with this in the TEEHR repo https://github.com/RTIInternational/teehr/tree/main. An example weight file has been provided [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor/data/weights). An example nwm forcing file can be found within the this [NOAA AWS bucket](https://noaa-nwm-pds.s3.amazonaws.com/index.html). forcing_short_range was used during development.


 ```
 python weight_generator.py <path to geopackage> <path to output weights to> <path to example NWM forcing file>
 ```

The weight generator will input an example NWM forcing netcdf to reference the NWM grid, a geopackage that contains all of the catchments the user wants weights for, and a file name for the weight file. Subsetted geopackages can be made with [subsetting](https://github.com/CIROH-UA/ngen-datastream/tree/main/subsetting)

## Configuration Sections

### 1. Forcing

Note! the *input options are the same associated with https://github.com/CIROH-UA/nwmurl

| Field             | Description              |
|-------------------|--------------------------|
| start_time        | Datetime of first nwm file (YYYYMMDDHHMM) |
| end_time          | Datetime of last nwm file  (YYYYMMDDHHMM) |
| nwm_file          | Path to a text file containing nwm file names. One filename per line. Any *input options |
| weight_file       | Weight file for the run. Accepts local absolute path, s3 URI or URL  |

### 2. Storage

The "storage" section contains parameters related to storage configuration.

| Field             | Description                       |
|-------------------|-----------------------------------|
| storage_type      | Type of storage (local or s3)     |
| output_bucket     | If storage_type = s3: output bucket for output, If storage_type = local: appened to output_path |
| output_path       | If storage_type = s3: prefix for output, If storage_type = local: absolute path for output, will default to cwd/date if left blank |
| output_file_type  | Output file type (e.g., csv, parquet)      |

### 3. Run
The "run" section contains parameters related to the execution of the application.

| Field             | Description                    |
|-------------------|--------------------------------|
| verbose           | Verbosity of the run           |
| collect_stats     | Collect forcing metadata       |
| proc_threads      | Number of data processing threads, defaults to 80% available cores |
| write_threads     | Number of writing threads, defaults to 100% available cores      |
| nfile_chunk       | Number of files to process each write,<br> set to greater than the number of nwm files unless memory constraints are reached, defaults to 1000000. Only set this if experiencing memory constraints due to large number of nwm forcing files |

## Example Configuration
```
{
    "forcing"  : {
        "start_date     : "",
        "end_date"     : "",
        "nwm_file"     : "",
        "weight_file"  : ""
    },

    "storage":{
        "storage_type"     : "local",
        "output_bucket"    : "",
        "output_path"      : "",
        "output_file_type" : "csv"
    },    

    "run" : {
        "verbose"       : true,
        "collect_stats" : true,
    }
}
