# Forcing Processor
Forcingprocessor converts National Water Model (NWM) forcing data into Next Generation National Water Model (ngen) forcing data. The motivation for this tool is NWM data is gridded and stored within netCDFs for each forecast hour. Ngen inputs this same forcing data, but in the format of per-catchment csv files that hold time series data. Forcingprocessor is driven by a configuration file that is explained, with an example, in detail below. The config argument accepts an s3 URL.

## Run the forcingprocessor
```
python forcingprocessor.py conf.json
```
For docker container: 
```
docker run --rm -v /path/to/configs:/mounted_dir forcingprocessor python /ngen-datastream/forcingprocessor/src/forcingprocessor.py /mounted_dir/conf_docker.json
```
File will be written out locally to mounted_dir/`output_path` if `storage_type` is "local".

## Run Notes
This tool is CPU, memory, and I/O intensive. For the best performance, run with `proc_threads` equal to than half of available cores and `write_threads` equal to the number of available cores. Best to experiment with your resources to find out what works best. These options default to 80% and 100% available cores respectively.

## nwm_file
A text file given to forcingprocessor that contains each nwm forcing file name. These can be URLs or local paths. This file can be generated with the [nwmurl tool](https://github.com/CIROH-UA/nwmurl) and a [generator script](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor/nwm_filenames_generator.py) that has been provided within this repo. The config argument accepts an s3 URL. 
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
In order to retrieve forcing data from a NWM grid for a given catchment, the indices (weights) of that catchment must be provided to the forcingprocessor in the weights file. The script will ingest every set of catchment weights and produce a corresponding forcings file. These weights can be generated manually from a geopackage https://noaa-owp.github.io/hydrofabric/articles/data_access.html with the [weight generator](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor/weight_generator.py). Also, tools are available to help with this in the TEEHR repo https://github.com/RTIInternational/teehr/tree/main. An example weight file has been provided [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor/data/weights). An example nwm forcing file can be found within the this [NOAA AWS bucket](https://noaa-nwm-pds.s3.amazonaws.com/index.html). forcing_short_range was used during development.

 ```
 python weight_generator.py <path to geopackage> <path to output weights to> <path to example NWM forcing file>
 ```

The weight generator will input an example NWM forcing netcdf to reference the NWM grid, a geopackage that contains all of the catchments the user wants weights for, and a file name for the weight file. Subsetted geopackages can be made with [subsetting](https://github.com/CIROH-UA/ngen-datastream/tree/main/subsetting)

## Configuration Sections

### 1. Forcing
| Field             | Description              |
|-------------------|--------------------------|
| start_time        | Datetime of first nwm file (YYYYMMDDHHMM) |
| end_time          | Datetime of last nwm file  (YYYYMMDDHHMM) |
| nwm_file          | Path to a text file containing nwm file names. One filename per line. Any *input options |
| weight_file       | Weight file for the run. Accepts local absolute path, s3 URI or URL  |

### 2. Storage

| Field             | Description                       |
|-------------------|-----------------------------------|
| storage_type      | Type of storage (local or s3)     |
| output_bucket     | If storage_type = s3: output bucket for output, If storage_type = local: appened to output_path |
| output_path       | If storage_type = s3: prefix for output, If storage_type = local: absolute path for output, will default to cwd/date if left blank |
| output_file_type  | Output file type (e.g., csv, parquet)      |

### 3. Run
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
        "start_date    : "",
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
