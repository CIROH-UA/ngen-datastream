# NextGen Datastream
The datastream automates the process of collecting and formatting input data for NextGen, orchestrating the NextGen run through NextGen In a Box (NGIAB), and handling outputs. In its current implementation, the datastream is a shell script that orchestrates each step in the process. 

## Disclaimer
This software is designed for deployment in HPC architecture and will consume the majority of resources by default. The intended use of this software is to take advantage of HPC hardware to solve the necessary computations quickly. While it is possible to run the datastream using resources available on a laptop by capping the number of allowed processes (via `NPROCS`), the internal algorithms were designed to perform best on a dedicated HPC host.

## Install
[Linux Install](https://github.com/CIROH-UA/ngen-datastream/blob/main/INSTALL.md)

## Run it
```
> ngen-datastream --help

Usage: ./ngen-datastream/scripts/stream.sh [options]
Either provide a datastream configuration file
  -c, --CONF-FILE           <Path to datastream configuration file>
or run with cli args
  -s, --START_DATE          <YYYYMMDDHHMM or "DAILY">
  -e, --END_DATE            <YYYYMMDDHHMM>
  -d, --DATA_PATH           <Path to write to>
  -r, --RESOURCE_PATH       <Path to resource directory>
  -t, --RELATIVE_TO         <Path to prepend to all paths>
  -S, --S3_MOUNT            <Path to mount s3 bucket to>
  -i, --SUBSET_ID_TYPE      <Hydrofabric id type>
  -I, --SUBSET_ID           <Hydrofabric id to subset>
  -v, --HYDROFABRIC_VERSION <Hydrofabric version>
  -n, --NPROCS              <Process limit> 
```
Example command for the the DAILY run
```
ngen-datastream --CONF_FILE conf_datastream_daily.sh
```
See [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/examples) for examples


## Explanation of cli args (variables in defined in `conf_datastream.sh`)
| Field               | Description              | Required |
|---------------------|--------------------------|------|
| START_DATE          | Start simulation time (YYYYMMDDHHMM) or "DAILY" | :white_check_mark: |
| END_DATE            | End simulation time  (YYYYMMDDHHMM) | :white_check_mark: |
| DATA_PATH           | Path to construct the datastream run. | :white_check_mark: |
| RESOURCE_PATH       | Folder name that contains the datastream resources. If not provided, datastream will create this folder with [default options](#defaults) |  |
| RELATIVE_TO         | Absolute path to be prepended to any other path given in configuration file |  |
| S3_MOUNT            | Path to mount S3 bucket to. datastream will copy outputs here. |
| SUBSET_ID_TYPE      | id type corresponding to "id" [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option) |   |
| SUBSET_ID           | catchment id to subset [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option) |   |
| HYDROFABRIC_VERSION | $\geq$ v20.1 [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option)  |
| NPROCS              | Maximum number of processes to use in any step of the datastream. Set this is not running on HPC |  |

## NextGen Datastream Directory Stucture
When the datastream is executed a folder of the structure below will be constructed at `DATA_PATH`
```
DATA-PATH/
│
├── datastream-configs/
│
├── datastream-resources/
|
├── ngen-run/
```
Each folder is explained below

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
Automatically generated with [defaults](#defaults) or copied from user defined `RESOURCE_PATH`. Holds the data files required to perform computations required by the datastream. 
#### Rules for manually building a `RESOURCE_PATH`
A user defined `RESOURCE_PATH` may take the form below. Only one file of each type is allowed (e.g. cannot have two geopackages). Not every file is required.
```
RESOURCE_PATH/
│
├── GEOPACKAGE
|
├── NWM_EXAMPLE_GRID_FILE
|
├── WEIGHT_FILE
|
├── CONF_NWMURL
│
├── NGEN-CONFIGS/
```

| File        |    Example link    | Description  | Naming |
|-------------|--------|--------------------------|-----|
| GEOPACKAGE | [nextgen_01.gpkg](https://lynker-spatial.s3.amazonaws.com/v20.1/gpkg/nextgen_01.gpkg) | Hydrofabric file of version $\geq$ v20.1 Ignored if subset hydrofabric options are set in datastream config. [See hfsubset for options](https://github.com/LynkerIntel/hfsubset) for generating your own. The datastream has hfsubset integrated. | *.gpkg |
| NWM_EXAMPLE_GRID_FILE | [202001021700.LDASIN_DOMAIN1](https://noaa-nwm-retrospective-3-0-pds.s3.amazonaws.com/CONUS/netcdf/FORCING/2020/202001021700.LDASIN_DOMAIN1) | Example forcings file used in weight calculation. Not needed if WEIGHT_FILE exists | nwm_example_grid_file.nc |
| WEIGHT_FILE | [weights.json](https://ngen-datastream.s3.us-east-2.amazonaws.com/resources_default/weights_w_cov.json) | [weights file description](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor#weight_file) | \*weights\*.json |
| CONF_NWMURL | [nwmurl_conf.json](https://github.com/CIROH-UA/ngen-datastream/blob/main/forcingprocessor/configs/conf_nwmurl_retro.json) | [nwmurl config file description](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor#nwm_file). Not required for `DAILY` runs | \*nwmurl\*.json |
| NGEN-CONFIGS | [ngen-configs/realization.json](https://ngen-datastream.s3.us-east-2.amazonaws.com/resources_default/ngen-configs/realization.json) | Any files required for ngen/NGIAB run. Copied into `DATA_PATH/ngen_run/configs` | ngen-configs/realization.json |

#### Defaults
The URI below holds the default resource directory for the datastream, which is used during the "daily" runs. This directory holds files for a standard NGIAB formulation over CONUS. Use `aws s3 ls s3://ngen-datastream/resources_default/` to inspect the files.

### `ngen-run/` 
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
 
#### Configuration directory `ngen-run/config/`

Model Configuration Example files: `config.ini`,`realization.json`
The realization file serves as the primary model configuration for the ngen framework. Downloand an example realization file [here](https://ngenresourcesdev.s3.us-east-2.amazonaws.com/ngen-run-pass/configs/realization.json). This file specifies which models/modules to run and with which parameters, run parameters like date and time, and hydrofabric specifications. If experiencing run-time errors, the realization file is the first place to check. Other files may be placed in this subdirectory that relate to internal-ngen-models/modules (`config.ini`). It is common to define variables like soil parameters in these files for ngen modules to use.

Hydrofabric Example files: `nextgen_01.gpkg`
NextGen requires a single geopackage file. This fle is the [hydrofabric](https://mikejohnson51.github.io/hyAggregate/) (spatial data). An example geopackage can be found [here](https://lynker-spatial.s3.amazonaws.com/v20/gpkg/nextgen_01.gpkg). Tools to subset a geopackage into a smaller domain can be found at [Lynker's hfsubset](https://github.com/LynkerIntel/hfsubset).

## Versioning
The ngen framework uses a merkel tree hashing algorithm to version each ngen run with [ht tool](https://github.com/aaraney/ht). This means that the changes a user makes to any input files in `ngen-run` will be tracked and diff'd against previous input directories. While an explaination of how awesome this is can be found [elsewhere](https://en.wikipedia.org/wiki/Merkle_tree), the important thing to know is the user must prepare a clean input directory (`ngen-run`) for each run they want to make. 

"Clean" means here that every file in the `ngen-run` is required for the immediate run the user intends to make. For instance, if the user creates a new realization configuration file, the old file must be removed before using `ngen-run` as an input directory to ngen. In other words, each configuration file type (realization, catchment, nexus, etc.) must be unique within `ngen-run`.
