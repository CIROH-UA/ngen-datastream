# NextGen Water Modeling Framework Datastream
`ngen-datastream` automates the process of collecting and formatting input data for NextGen, orchestrating the NextGen run through NextGen In a Box (NGIAB), and handling outputs. This software allows users to run NextGen in an efficient, _relatively_ painless, and reproducible fashion.

`Hardware` - While `ngen-datastream` will run locally on a user's laptop, it is often the case that NextGen runs are so large that running on a dedicated host will be optimal. 

`Speed` - Complete datastream run for a day over VPU 09 takes about 7 minutes on a free-tier AWS t2.2xlarge ec2 instance (8vCPU, 32GB) with CFE, PET, and NOM NextGen configuration. 

## [Install](https://github.com/CIROH-UA/ngen-datastream/blob/main/INSTALL.md)

## Run it
`ngen-datastream` can be executed using cli args or a configuration file.
```
> ./ngen-datastream/scripts/stream.sh --help

Usage: ./ngen-datastream/scripts/stream.sh [options]
Either provide a datastream configuration file
  -c, --CONF_FILE          <Path to datastream configuration file>
or run with cli args
  -s, --START_DATE          <YYYYMMDDHHMM or "DAILY">
  -e, --END_DATE            <YYYYMMDDHHMM>
  -d, --DATA_PATH           <Path to write to>
  -r, --RESOURCE_PATH       <Path to resource directory>
  -g, --GEOPACAKGE          <Path to geopackage file>
  -G, --GEOPACAKGE_ATTR     <Path to geopackage attributes file>
  -S, --S3_MOUNT            <Path to mount s3 bucket to>
  -o, --S3_PREFIX           <File prefix within s3 mount>
  -i, --SUBSET_ID_TYPE      <Hydrofabric id type>
  -I, --SUBSET_ID           <Hydrofabric id to subset>
  -v, --HYDROFABRIC_VERSION <Hydrofabric version>
  -n, --NPROCS              <Process limit>
  -D, --DOMAIN_NAME         <Name for spatial domain>
  -h, --host_type           <Host type>
```
Example command for the the DAILY run:
```
./ngen-datastream/scripts/stream.sh --CONF_FILE conf_datastream_daily.sh
```
See [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/examples) for examples


## Explanation of cli args (variables in defined in `conf_datastream.sh`)
| Field               | Description              | Required |
|---------------------|--------------------------|------|
| START_DATE          | Start simulation time (YYYYMMDDHHMM) or "DAILY" | :white_check_mark: |
| END_DATE            | End simulation time  (YYYYMMDDHHMM) | :white_check_mark: |
| DATA_PATH           | Path to construct the datastream run. | :white_check_mark: |
| RESOURCE_PATH       | Path to directory that contains the datastream resources. This directory allows the user to place the several required files into a single directory and simply point `ngen-datastream` to it with this arg. This is folder is generated at `DATA_PATH/datastream-resources` during a `ngen-datastream` execution and can be reused in future runs. More explanation [here](#datastream-resources)|  |
| GEOPACKAGE          | Path to hydrofabric, can be s3URI, URL, or local file | Required here or file exists in `RESOURCE_PATH/ngen-configs` |
| GEOPACKAGE_ATTR     | Path to hydrofabric attributes, can be s3URI, URL, or local file | Required here or file exists in `RESOURCE_PATH/ngen-configs` |
| S3_MOUNT            | Path to mount S3 bucket to. `ngen-datastream` will copy outputs here. |  |
| S3_PREFIX           | Prefix to prepend to all files when copying to s3 |
| SUBSET_ID_TYPE      | id type corresponding to "id" [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option) |   |
| SUBSET_ID           | catchment id to subset [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option) |   |
| HYDROFABRIC_VERSION | $\geq$ v20.1 [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option)  |
| NPROCS              | Maximum number of processes to use in any step of  `ngen-datastream`. Defaults to `nprocs - 2` |  |
| DOMAIN_NAME         | Name for spatial domain in run, stripped from gpkg if not supplied |  |
| HOST_TYPE           | The type or name of the host on which ngen-datastream is running, will autofill with ec2 instance type if running on AWS. |  |


## `ngen-datastream` Output Directory Structure
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

Automatically generated. Holds all of the configuration files the datastream needs in order to run. `datastream-configs/` is the first place to look to confirm that a datastream run has been executed according to the user's specifications. 
Example directory:
```
datastream-configs/
│
├── conf_datastream.json
│
├── conf_fp.json
|
├── conf_nwmurl.json
|
├── profile.txt
```
### `RESOURCE_PATH` and `datastream-resources/` 
`datastream-resources/` holds all the input data files required to perform the various computations `ngen-datastream` performs. This folder is generated during a `ngen-datastream` execution This folder is not required as input, but can be a useful method for supplying ngen-datastream with files like geopackages, realization files, and forcing weights.

Examples of the application of the resource directory:
1) Repeated executions. `ngen-datastream` will retrieve files (that are given as arguements) remotely, however this can take time depending on the networking between the data source and host. Storing these files locally in `RESOURCE_PATH` for repeated runs will save time and network bandwith.
2) Communicating runs. ngen-datastream versions everything in `DATA_PATH`, which means a single hash corresponds to a unique `RESOURCE_PATH`, which allows users to quickly identify potential differences between `ngen-datastream` input data.

#### Rules for manually building a `RESOURCE_PATH`
A user defined `RESOURCE_PATH` may take the form below. Only one file of each type is allowed (e.g. cannot have two geopackages). Not every file is required.
```
RESOURCE_PATH/
|
├── ngen-configs/
|   │
|   ├── nextgen_01.gpkg
|   │
|   ├── nextgen_01.parquet   
|   │
|   ├── realization.json 
|
├── weights.json
|
├── conf_nwmurl.json
  
```

| File Type        |    Example link    | Description  | Naming |
|-------------|--------|--------------------------|-----|
| GEOPACKAGE | [ngen-configs/nextgen_01.gpkg](https://lynker-spatial.s3.amazonaws.com/v20.1/gpkg/nextgen_01.gpkg) | Hydrofabric file of version $\geq$ v20.1 Ignored if subset hydrofabric options are set in datastream config. See [Lynker-Spatial](https://www.lynker-spatial.com/#v20.1/gpkg/) for complete VPU geopackages or [hfsubset](https://github.com/LynkerIntel/hfsubset) for generating your own custom domain. `hfsubset` can be invoked indirectly through `ngen-datastream` through the subsetting args. | *.gpkg |
| GEOPACKGE_ATTR | [ngen-configs/nextgen_01.parquet ](https://lynker-spatial.s3.amazonaws.com/v20.1/model_attributes/nextgen_09.parquet) | See [Lynker-Spatial](https://www.lynker-spatial.com/#v20.1/model_attributes/) for geopackage attributes files. Necessary for the creation of ngen bmi module config files. | nwm_example_grid_file.nc |
| REALIZATION | [ngen-configs/realization.json](https://ngen-datastream.s3.us-east-2.amazonaws.com/resources_default/ngen-configs/realization.json) | ngen realization file. | ngen-configs/realization.json |
| WEIGHTS_FILE | [weights.json](https://ngen-datastream.s3.us-east-2.amazonaws.com/resources_small/weights.json) | [weights file description](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor#weight_file) | \*weights\*.json |
| CONF_NWMURL | [nwmurl_conf.json](https://github.com/CIROH-UA/ngen-datastream/blob/main/forcingprocessor/configs/conf_nwmurl_retro.json) | [nwmurl config file description](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor#nwm_file). Not required for `DAILY` runs | \*nwmurl\*.json |

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
