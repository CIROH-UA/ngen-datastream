# NextGen Water Modeling Framework Datastream
`ngen-datastream` automates the process of collecting and formatting input data for NextGen, orchestrating the NextGen run through NextGen In a Box (NGIAB), and handling outputs. This software allows users to run NextGen in an efficient, _relatively_ painless, and reproducible fashion.

## Getting Started
* **Installation:** Follow the step-by-step instructions in the [Installation Guide](https://github.com/CIROH-UA/ngen-datastream/blob/main/INSTALL.md) to set up `ngen-datastream` on your system.
* **Usage:** Learn how to use `ngen-datastream` effectively by referring to the comprehensive [Usage Guide](https://github.com/CIROH-UA/ngen-datastream/blob/main/USAGE.md).

## Run it
`ngen-datastream` can be executed using cli args or a configuration file. Not all arguments are requried. 
```
> cd ngen-datastream && ./scripts/stream.sh --help

Usage: ./ngen-datastream/scripts/stream.sh [options]
Either provide a datastream configuration file
  -c, --CONF_FILE           <Path to datastream configuration file> 
or run with cli args
  -s, --START_DATE          <YYYYMMDDHHMM or "DAILY"> 
  -e, --END_DATE            <YYYYMMDDHHMM> 
  -D, --DOMAIN_NAME         <Name for spatial domain> 
  -g, --GEOPACAKGE          <Path to geopackage file> 
  -G, --GEOPACKAGE_ATTR     <Path to geopackage attributes file> 
  -i, --SUBSET_ID_TYPE      <Hydrofabric id type>  
  -I, --SUBSET_ID           <Hydrofabric id to subset>  
  -v, --HYDROFABRIC_VERSION <Hydrofabric version> 
  -R, --REALIZATION         <Path to realization file> 
  -d, --DATA_PATH           <Path to write to> 
  -r, --RESOURCE_PATH       <Path to resource directory> 
  -f, --FORCINGS            <Path to forcings directory or tarball> 
  -S, --S3_MOUNT            <Path to mount s3 bucket to>  
  -o, --S3_PREFIX           <File prefix within s3 mount>
  -n, --NPROCS              <Process limit> 
```
This command will execute a 24 hour NextGen simulation over VPU 09 with CFE, SLOTH, PET, and NOM configuration distributed over 8 processes. See more [examples](https://github.com/CIROH-UA/ngen-datastream/blob/main/examples).
```
./scripts/stream.sh \
  -s 202405200100 \
  -e 202405210000 \
  -d $(pwd)/data/datastream_test \
  -g https://lynker-spatial.s3.amazonaws.com/hydrofabric/v20.1/gpkg/nextgen_09.gpkg \
  -G https://lynker-spatial.s3.amazonaws.com/hydrofabric/v20.1/model_attributes/nextgen_09.parquet \
  -R $(pwd)/configs/ngen/realization_cfe_sloth_pet_nom.json \
  -n 8
```

## Explanation of cli args (variables in defined in `conf_datastream.sh`)
| Field               | Description              | Required |
|---------------------|--------------------------|------|
| START_DATE          | Start simulation time (YYYYMMDDHHMM) or "DAILY" | :white_check_mark: |
| END_DATE            | End simulation time  (YYYYMMDDHHMM) | :white_check_mark: |
| DOMAIN_NAME         | Name for spatial domain in run, stripped from gpkg if not supplied |  |
| GEOPACKAGE          | Path to hydrofabric, can be s3URI, URL, or local file | Required here or file exists in `RESOURCE_PATH/ngen-configs` |
| GEOPACKAGE_ATTR     | Path to hydrofabric attributes, can be s3URI, URL, or local file | Required here or file exists in `RESOURCE_PATH/ngen-configs` |
| SUBSET_ID_TYPE      | id type corresponding to "id" [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option) |   |
| SUBSET_ID           | catchment id to subset [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option) |   |
| HYDROFABRIC_VERSION | $\geq$ v20.1 [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option)  |
| REALIZATION         | Path to NextGen realization file | Required here or file exists in `RESOURCE_PATH/ngen-configs` |
| DATA_PATH           | Absolute local path to construct the datastream run. | :white_check_mark: |
| RESOURCE_PATH       | Path to directory that contains the datastream resources. This directory allows the user to place the several required files into a single directory and simply point `ngen-datastream` to it. This is folder is generated at `DATA_PATH/datastream-resources` during a `ngen-datastream` execution and can be reused in future runs. More explanation [here](#datastream-resources)|  |
| FORCINGS            | Path to local directory containing nwm files or tarball that contains ngen forcings csvs/parquets|  |
| S3_MOUNT            | Path to mount S3 bucket to. `ngen-datastream` will copy outputs here. |  |
| S3_PREFIX           | Prefix to prepend to all files when copying to s3 |
| NPROCS              | Maximum number of processes to use in any step of  `ngen-datastream`. Defaults to `nprocs - 2` |  |



## `ngen-datastream` Output Directory Structure
When the datastream is executed a folder of the structure below will be constructed at `DATA_PATH`
```
DATA-PATH/
│
├── datastream-metadata/
│
├── datastream-resources/
|
├── ngen-run/
```
Each folder is explained below

### `datastream-metadata/` 

Automatically generated. Holds all of the metadata and configuration files the datastream needs in order to run. `datastream-metadata/` is the first place to look to confirm that a datastream run has been executed according to the user's specifications. 
Example directory:
```
datastream-metadata/
│
├── conf_datastream.json
│
├── conf_fp.json
|
├── conf_nwmurl.json
|
├── profile.txt
|
├── filenamelist.txt
|
├── realization.json
```
### `RESOURCE_PATH` (`datastream-resources/`)
`datastream-resources/` holds all the input data files required to perform the various computations `ngen-datastream` performs. This folder is not required as input, but will be a faster method for running ngen-datastream repeatedly over a given spatial domain.

Examples of the application of the resource directory:
1) Repeated executions. `ngen-datastream` will retrieve files (that are given as arguements) remotely, however this can take time depending on the networking between the data source and host. Storing these files locally in `RESOURCE_PATH` for repeated runs will save time and network bandwith. In addition, this saves on compute required to build input files from scratch.
2) Communicating runs. ngen-datastream versions everything in `DATA_PATH`, which means a single hash corresponds to a unique `RESOURCE_PATH`, which allows users to quickly identify potential differences between `ngen-datastream` input data.

#### Guide for building a `RESOURCE_PATH`
The easiest way to create a reusable resource directory is to execute `ngen-datastream` and save `$DATA_PATH/datastream-resources` for later use. A user defined `RESOURCE_PATH` may take the form below. Only one file of each type is allowed (e.g. cannot have two geopackages).
```
RESOURCE_PATH/
|
├── weights.json
|
├── ngen-configs/
|   │
|   ├── nextgen_01.gpkg
|   │
|   ├── nextgen_01.parquet   
|   │
|   ├── realization.json 
|   │
|   ├── ngen-bmi-configs.tar.gz
|
├── nwm-forcings/
|   ├── nwm.t00z.medium_range.forcing.f001.conus
|   ├── ...
```
** nwm-forcings is only saved to `RESOURCE_PATH` if local nwm forcings files were provided during execution. `ngen-datastream` will not store forcings files that were accessed remotely.

| File Type        |    Example link    | Description  | Naming |
|-------------|--------|--------------------------|-----|
| GEOPACKAGE | [ngen-configs/nextgen_01.gpkg](https://lynker-spatial.s3.amazonaws.com/v20.1/gpkg/nextgen_01.gpkg) | Hydrofabric file of version $\geq$ v20.1 Ignored if subset hydrofabric options are set in datastream config. See [Lynker-Spatial](https://www.lynker-spatial.com/#v20.1/gpkg/) for complete VPU geopackages or [hfsubset](https://github.com/LynkerIntel/hfsubset) for generating your own custom domain. `hfsubset` can be invoked indirectly through `ngen-datastream` through the subsetting args. | *.gpkg |
| GEOPACKGE_ATTR | [ngen-configs/nextgen_01.parquet ](https://lynker-spatial.s3.amazonaws.com/v20.1/model_attributes/nextgen_09.parquet) | See [Lynker-Spatial](https://www.lynker-spatial.com/#v20.1/model_attributes/) for geopackage attributes files. Necessary for the creation of ngen bmi module config files. | nwm_example_grid_file.nc |
| REALIZATION | [ngen-configs/realization.json](https://ngen-datastream.s3.us-east-2.amazonaws.com/resources_default/ngen-configs/realization.json) | ngen realization file. | ngen-configs/realization.json |
| WEIGHTS_FILE | [weights.json](https://ngen-datastream.s3.us-east-2.amazonaws.com/resources_small/weights.json) | [weights file description](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor#weight_file) | \*weights\*.json |

#### Defaults
The URI below holds the default resource directory for the datastream, which is used during development runs. This directory holds files for a standard NGIAB formulation over VPU_09. Use `aws s3 ls s3://ngen-datastream/resources_small/` to inspect the files.

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

Hydrofabric Example files: `nextgen_01.gpkg`,`nextgen_01.parquet`
NextGen requires a single geopackage file. This fle is the [hydrofabric](https://mikejohnson51.github.io/hyAggregate/) (spatial data). An example geopackage can be found [here](https://lynker-spatial.s3.amazonaws.com/v20/gpkg/nextgen_01.gpkg). Tools to subset a geopackage into a smaller domain can be found at [Lynker's hfsubset](https://github.com/LynkerIntel/hfsubset). `ngen-datastream` requires a geopackage attributes file, `nextgen_01.parquet`, which is required for generating ngen bmi module configuration files.

## Versioning
`ngen-datstream` uses a merkel tree hashing algorithm to version each execution with [merkdir](https://github.com/makew0rld/merkdir). This means all input and output files in a `ngen-datastream` execution will be hashed in such a way that tracking minute changes among millions of files is trivial.

## License
`ngen-datastream` is distributed under [GNU General Public License v3.0 or later](LICENSE.md)
