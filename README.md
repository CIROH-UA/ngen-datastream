# NextGen Water Modeling Framework Datastream
`ngen-datastream` automates the process of collecting and formatting input data for NextGen, orchestrating the NextGen run through NextGen In a Box (NGIAB), and handling outputs. This software allows users to run NextGen in an efficient, _relatively_ painless, and reproducible fashion.

## Getting Started
* **Installation:** Follow the step-by-step instructions in the [Installation Guide](https://github.com/CIROH-UA/ngen-datastream/blob/main/INSTALL.md) to set up `ngen-datastream` on your system.
* **Usage:** Learn how to use `ngen-datastream` effectively by referring to the comprehensive [Usage Guide](https://github.com/CIROH-UA/ngen-datastream/blob/main/USAGE.md).

## Run it
`ngen-datastream` can be executed using cli args or a configuration file. Not all arguments are requried. 
```
> cd ngen-datastream && ./scripts/stream.sh --help

Usage: ./scripts/stream.sh [options]
Either provide a datastream configuration file
  -c, --CONF_FILE           <Path to datastream configuration file> 
or run with cli args
  -s, --START_DATE          <YYYYMMDDHHMM or "DAILY"> 
  -e, --END_DATE            <YYYYMMDDHHMM> 
  -D, --DOMAIN_NAME         <Name for spatial domain> 
  -g, --GEOPACAKGE          <Path to geopackage file> 
  -G, --GEOPACKAGE_ATTR     <Path to geopackage attributes file> 
  -w, --HYDROFABRIC_WEIGHTS <Path to hydrofabric weights parquet> 
  -I, --SUBSET_ID           <Hydrofabric id to subset>  
  -i, --SUBSET_ID_TYPE      <Hydrofabric id type>  
  -v, --HYDROFABRIC_VERSION <Hydrofabric version> 
  -R, --REALIZATION         <Path to realization file> 
  -d, --DATA_DIR            <Path to write to> 
  -r, --RESOURCE_DIR        <Path to resource directory> 
  -f, --NWM_FORCINGS_DIR    <Path to nwm forcings directory> 
  -F, --NGEN_FORCINGS       <Path to ngen forcings tarball> 
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

## Explanation of cli args (or variables in defined in `CONF_FILE`)
| Field               | Description              | Required |
|---------------------|--------------------------|------|
| START_DATE          | Start simulation time (YYYYMMDDHHMM) or "DAILY" | :white_check_mark: |
| END_DATE            | End simulation time  (YYYYMMDDHHMM) | :white_check_mark: |
| DOMAIN_NAME         | Name for spatial domain in run, stripped from gpkg if not supplied |  |
| GEOPACKAGE          | Path to hydrofabric, can be s3URI, URL, or local file | Required here or file exists in `RESOURCE_DIR/config` |
| GEOPACKAGE_ATTR     | Path to hydrofabric attributes, can be s3URI, URL, or local file | Required here or file exists in `RESOURCE_DIR/config` |
| HYDROFABRIC_WEIGHTS | Indices relative to the nwm forcings grid used to calculate catchment averaged values. Provided directly from the hydrofabric  | Required here or file exists in `RESOURCE_DIR/config`only if GEOPACKAGE and GEOPACKAGE_ATTR files were created manually via the hydrofabric. If processing over a VPU, the datastream will make queries itself to the CONUS weights in Lynker Spatial. |
| SUBSET_ID_TYPE      | id type corresponding to "id" [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option) | Required here if user is not providing GEOPACKAGE and GEOPACKAGE_ATTR. |
| SUBSET_ID           | catchment id to subset [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option) | Required here if user is not providing GEOPACKAGE and GEOPACKAGE_ATTR.  |
| HYDROFABRIC_VERSION | $\geq$ v20.1 [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option)  | Required here if user is not providing GEOPACKAGE and GEOPACKAGE_ATTR. | 
| REALIZATION         | Path to NextGen realization file | Required here or file exists in `RESOURCE_DIR/config` |
| DATA_DIR           | Absolute local path to construct the datastream run. | :white_check_mark: |
| RESOURCE_DIR       | Path to directory that contains the datastream resources. More explanation [here](#resource_dir-datastream-resources). |  |
| NWM_FORCINGS_DIR | Path to local directory containing nwm files. Alternatively, thse file could be stored in RESOURCE_DIR a nwm-forcings. |  |
| FORCINGS            | Path to local ngen forcings tarball which holds csv's. Alternatively, this file could  be stored in RESOURCE_DIR at ngen-forcings. |  |
| S3_MOUNT            | Path to mount S3 bucket to. `ngen-datastream` will copy outputs here. |  |
| S3_PREFIX           | Prefix to prepend to all files when copying to s3 |
| NPROCS              | Maximum number of processes to use in any step of  `ngen-datastream`. Defaults to `nprocs - 2` |  |



## `ngen-datastream` Output Directory Structure
When the datastream is executed a folder of the structure below will be constructed at `DATA_DIR`
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

Holds metadata about the `ngen-datastream` excution that allows for a relatively condensed view of how the execution was performed. 
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
| File Type | Path in Resource Directory | Description | Naming |
|-------------|--------|----------|-----|
| DATASTREAM CONFIGURATION | datastream-metadata/conf_datastream.json | Holds metadata about the execution | conf_datastream.json |
| FORCING PROCESSOR CONFIGURATION | datastream-metadata/conf_fp.json | Configuration file for forcingprocessor. See [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor#example-confjson) | conf_fp.json |
| NWM URL CONFIGURATION | datastream-metadata/conf_nwmurl.json | Configuration file for nwmurl. See [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor#nwm_file) | conf_nwmurl.json |
| PROFILE | datastream-metadata/profile.txt | Datetime print statements that allow for profiling each step | profile.txt |
| FILENAME LIST | datastream-metadata/filenamelist.txt | Local file paths or URLs to NWM forcings. Generated by [nwmurl](https://github.com/CIROH-UA/nwmurl). | filenamelist.txt |
| REALIZATION | datastream-metadata/realization.json | NextGen configuration file. See [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/configs/ngen/realization_cfe_sloth_pet_nom.json) | realization.json |

### `RESOURCE_DIR` (`datastream-resources/`)
`datastream-resources/` holds all the input data files required to perform the various computations `ngen-datastream` performs. This folder is not required as input, but will be a faster method for running ngen-datastream repeatedly over a given spatial or time domain.

Examples of the application of the resource directory:
1) Repeated executions. `ngen-datastream` will retrieve files (that are given as arguements) remotely, however this can take time depending on the networking between the data source and host. Storing these files locally in `RESOURCE_DIR` for repeated runs will save time and network bandwith. In addition, this saves on compute required to build input files from scratch.
2) Communicating runs. ngen-datastream versions everything in `DATA_DIR`, which means a single hash corresponds to a unique `RESOURCE_DIR`, which allows users to quickly identify potential differences between `ngen-datastream` input data.

#### Guide for building a `RESOURCE_DIR`
The easiest way to create a reusable resource directory is to execute `ngen-datastream` and save `DATA_DIR/datastream-resources` for later use. A user defined `RESOURCE_DIR` may take the form below. Only one file of each type is allowed (e.g. cannot have two geopackages or two realizations). Not every file is required. `ngen-datastream` will generate all required files by default, but will skip those steps if corresponding files exist in the resource directory.
```
RESOURCE_DIR/
|
├── config/
|   │
|   ├── ngen-bmi-configs.tar.gz
|   │
|   ├── realization.json 
|   
├── datastream
|   |
|   ├── partitions.json
|   │
|   ├── weights.json
|
|── hydrofabric
|   |
|   |── nextgen_01.gpkg
|   │
|   ├── nextgen_01.parquet
|   │
|   ├── weights.parquet
|
├── nwm-forcings/
|   |
|   ├── nwm.t00z.medium_range.forcing.f001.conus
|   |
|   ├── ...
|
├── ngen-forcings/
|   |
|   ├── forcings.tar.gz
|
```

| File Type | Path in Resource Directory | Example Link | Description | Naming |
|-------------|--------|-------------|----------|-----|
| BMI CONFIGURATION | config/ngen-bmi-configs.tar.gz |  | tarball holding BMI module configuration files defined in realization file. | ngen-bmi-configs.tar.gz |
| REALIZATION | config/realization.json | [link](https://github.com/CIROH-UA/ngen-datastream/blob/main/configs/ngen/realization_cfe_sloth_pet_nom.json) | NextGen configuration | \*realization\*.json |
| GEOPACKAGE | hydrofabric/nextgen_01.gpkg | [link](https://lynker-spatial.s3.amazonaws.com/v20.1/gpkg/nextgen_01.gpkg) | Hydrofabric file of version $\geq$ v20.1 Ignored if subset hydrofabric options are set in datastream config. See [Lynker-Spatial](https://www.lynker-spatial.com/#v20.1/gpkg/) for complete VPU geopackages or [hfsubset](https://github.com/LynkerIntel/hfsubset) for generating your own custom domain. `hfsubset` can be invoked indirectly through `ngen-datastream` through the subsetting args. | *.gpkg |
| GEOPACKGE_ATTR | hydrofabric/nextgen_01.parquet | [link](https://lynker-spatial.s3.amazonaws.com/v20.1/model_attributes/nextgen_09.parquet) | See [Lynker-Spatial](https://www.lynker-spatial.com/#v20.1/model_attributes/) for geopackage attributes files. Necessary for the creation of ngen bmi module config files. | *.parquet |
| WEIGHTS | hydrofabric/weights.parquet | [link](https://lynker-spatial.s3.amazonaws.com/hydrofabric/v20.1/forcing_weights.parquet) | Indices relative to the nwm forcings grid used to calculate catchment averaged values. | \*weights\*.parquet |
| FORCINGS | nwm-forcings/*.nc | [link](https://noaa-nwm-retrospective-3-0-pds.s3.amazonaws.com/CONUS/netcdf/FORCING/2019/201901010000.LDASIN_DOMAIN1) | NetCDF National Water Model forcing files. These are not saved to the resource directory by default. | *.nc |
| FORCINGS | ngen-forcings/*.tar.gz |  | tarball holding ngen forcing csv's. This is not saved to the resource directory by default, but will be located at `DATA_DIR/ngen-run/forcings/forcings.tar.gz`  | *.tar.gz |
| PARTITIONS | datastream/patitions_$NPROCS.json | | File generated by the NextGen framework to distribute processing by spatial domain. | \*partitions\*.json |
| WEIGHTS | datastream/weights.json | |  [weights file description](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor#weight_file) | \*weights\*.json |


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
The realization file serves as the primary model configuration for the ngen framework. Downloand an example realization file [here](https://ngenresourcesdev.s3.us-east-2.amazonaws.com/ngen-run-pass/config/realization.json). This file specifies which models/modules to run and with which parameters, run parameters like date and time, and hydrofabric specifications. If experiencing run-time errors, the realization file is the first place to check. Other files may be placed in this subdirectory that relate to internal-ngen-models/modules (`config.ini`). It is common to define variables like soil parameters in these files for ngen modules to use.

Hydrofabric Example files: `nextgen_01.gpkg`,`nextgen_01.parquet`
NextGen requires a single geopackage file. This fle is the [hydrofabric](https://mikejohnson51.github.io/hyAggregate/) (spatial data). An example geopackage can be found [here](https://lynker-spatial.s3.amazonaws.com/v20/gpkg/nextgen_01.gpkg). Tools to subset a geopackage into a smaller domain can be found at [Lynker's hfsubset](https://github.com/LynkerIntel/hfsubset). `ngen-datastream` requires a geopackage attributes file, `nextgen_01.parquet`, which is required for generating ngen bmi module configuration files.

## Versioning
`ngen-datstream` uses a merkel tree hashing algorithm to version each execution with [merkdir](https://github.com/makew0rld/merkdir). This means all input and output files in a `ngen-datastream` execution will be hashed in such a way that tracking minute changes among millions of files is trivial.

## License
`ngen-datastream` is distributed under [GNU General Public License v3.0 or later](LICENSE.md)
