# NextGen Datastream
The datastream automates the process of collecting and formatting input data for NextGen, orchestrating the NextGen run through NextGen In a Box (NGIAB), and handling outputs. In it's current implementation, the datastream is a shell script that orchestrates each step in the process. 

## Install
If you'd like to run the stream, clone this repo and execute the command below. The stream will handle initialization and installation of the datastream tools. To utilize the individual tools in the stream, see their respective readme's for installation instructions.

## Run it with config file
```
/ngen-datastream/scripts/stream.sh --conf-file /ngen-datastream/configs/conf_datastream_daily.sh
```
See [config  directory](#datastream-configs) for examples

## Run it with cli args
```
/ngen-datastream/scripts/stream.sh /ngen-datastream/configs/conf_datastream_daily.sh \
  --start-date "" \
  --end-date "" \
  --data-path "" \
  --resource-path"" \
  --relative-to "" \
  --id-type "" \
  --id "" \
  --version ""
```

## Explanation of cli args or variables in  `conf_datastream.sh`
| Field               | Description              | Required |
|---------------------|--------------------------|------|
| START_DATE          | Start simulation time (YYYYMMDDHHMM) | :white_check_mark: |
| END_DATE            | End simulation time  (YYYYMMDDHHMM) | :white_check_mark: |
| DATA_PATH           | Name used in constructing the parent directory of the datastream. Must not exist prior to datastream run | :white_check_mark: |
| RESOURCE_PATH       | Folder name that contains the datastream resources. If not provided, datastream will create this folder with [default options](#datastream-resources-defaults) |  |
| RELATIVE_TO         | Absolute path to be prepended to any other path given in configuration file |  |
| SUBSET_ID_TYPE      | id type corresponding to "id" [See hfsubset for options](https://github.com/LynkerIntel/hfsubset) |   |
| SUBSET_ID           | catchment id to subset. If not provided, spatial domain is set to CONUS [See hfsubset for options](https://github.com/LynkerIntel/hfsubset) |   |
| HYDROFABRIC_VERSION |  [See hfsubset for options](https://github.com/LynkerIntel/hfsubset)  | hydrofabric version |

## NextGen Datastream Directory Stucture
```
data_dir/
│
├── datastream-configs/
│
├── datastream-resources/
|
├── ngen-run/
```
### `ngen-run/` 
Automatically generated. Follows the directory structure described [here](#nextgen-run-directory-structure).
### `datastream-configs/` 
Automatically generated. Holds all of the configuration files the datastream needs in order to run. Note! The datastream can modify `conf_datastream.json` and generate it's own internal configs. `datastream-configs/` is the first place to look to confirm that a datastream run has been executed according to the user's specifications. 
Example directory:
```
datastream-configs/
│
├── conf_datastream.json
│
├── conf_forcingprocessor.json
|
├── conf_nwmurl.json
```
### `datastream-resources/` 
Copied into `data_dir` if user supplied, generated with defaults if not. Holds the data files required to perform computations required by the datastream. The user can supply this directory by pointing the configuration file to `resource_dir`. If not given by the user, datastream will generate this folder with these [defaults](#resource_dir). If the user executes the stream in this way, there is no control over the spatial domain. 
```
datastream-resources/
│
├── ngen-configs/
│
├── <your-geopackage>.gpkg
|
├── <nwm-example-grid-file>.nc
```
#### `ngen-configs/` holds all non-hydrofabric configuration files for NextGen (`realizion.json`,`config.ini`)

#### `datastream-resources/` Defaults
```
GRID_FILE_DEFAULT="https://ngenresourcesdev.s3.us-east-2.amazonaws.com/nwm.t00z.short_range.forcing.f001.conus.nc"
NGEN_CONF_DEFAULT="https://ngenresourcesdev.s3.us-east-2.amazonaws.com/config.ini"
NGEN_REAL_DEFAULT="https://ngenresourcesdev.s3.us-east-2.amazonaws.com/daily_run_realization.json"
WEIGHTS_DEFAULT="https://ngenresourcesdev.s3.us-east-2.amazonaws.com/weights_conus_v21.json"https://lynker-spatial.s3.amazonaws.com/v20.1/conus.gpkg

```

### Useful Hacks
To create a run for today, the user just needs to set `start_date` to `"DAILY"`. The stream will automatically set the time parameters to generate 24 hours worth of NextGen output data for the current day.

## NextGen Run Directory Structure
Running NextGen requires building a standard run directory complete with only the necessary files. The datastream constructs this automatically, but can be manually built as well. Below is an explanation of the standard. Reference for discussion of the standard [here](https://github.com/CIROH-UA/NGIAB-CloudInfra/pull/17). 

A NextGen run directory `ngen-run` is composed of three necessary subfolders `config, forcings, outputs` and an optional fourth subfolder `metadata`.

```
ngen-run/
│
├── config/
│
├── forcings/
|
├── metadata/
│
├── outputs/
```

The `ngen-run` directory contains the following subfolders:

- `config`:  model configuration files and hydrofabric configuration files. A deeper explanation [here](#Configuration-directory)
- `forcings`: catchment-level forcing timeseries files. These can be generated with the [forcingprocessor](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor). Forcing files contain variables like wind speed, temperature, precipitation, and solar radiation.
- `metadata` is an optional subfolder. This is programmatically generated and it used within to ngen. Do not edit this folder.
- `outputs`: This is where ngen will place the output files.
 
### Configuration directory `ngen-run/config/`

Model Configuration Example files: `config.ini`,`realization.json`
The realization file serves as the primary model configuration for the ngen framework. Downloand an example realization file [here](https://ngenresourcesdev.s3.us-east-2.amazonaws.com/ngen-run-pass/configs/realization.json). This file specifies which models/modules to run and with which parameters, run parameters like date and time, and hydrofabric specifications. If experiencing run-time errors, the realization file is the first place to check. Other files may be placed in this subdirectory that relate to internal-ngen-models/modules (`config.ini`). It is common to define variables like soil parameters in these files for ngen modules to use.

Hydrofabric Example files: `nextgen_01.gpkg` OR `catchments.geojson`, `nexus.geojson`,`crosswalk.json`, `flowpaths.json` ,`flowpath_edit_list.json`
Up until recently (Dec 2023), NextGen required geojson formatted hydrofabric and this formatting is still accepted. Now, NextGen also accepts a single geopackage file.
These files contain the [hydrofabric](https://mikejohnson51.github.io/hyAggregate/) (spatial data). An example geopackage can be found [here](https://lynker-spatial.s3.amazonaws.com/v20/gpkg/nextgen_01.gpkg). Tools to create these files can be found at [Lynker's hfsubset](https://github.com/LynkerIntel/hfsubset).

## Versioning
The ngen framework uses a merkel tree hashing algorithm to version each ngen run with [ht tool](https://github.com/aaraney/ht). This means that the changes a user makes to any input files in `ngen-run` will be tracked and diff'd against previous input directories. While an explaination of how awesome this is can be found [elsewhere](https://en.wikipedia.org/wiki/Merkle_tree), the important thing to know is the user must prepare a clean input directory (`ngen-run`) for each run they want to make. 

"Clean" means here that every file in the `ngen-run` is required for the immediate run the user intends to make. For instance, if the user creates a new realization configuration file, the old file must be removed before using `ngen-run` as an input directory to ngen. In other words, each configuration file type (realization, catchment, nexus, etc.) must be unique within `ngen-run`.
