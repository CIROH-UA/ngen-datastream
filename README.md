# NextGen Datastream
The datastream automates the process of collecting and formatting input data for NextGen, orchestrating the NextGen run through NextGen In a Box (NGIAB), and handling outputs. In it's current implementation, the datastream is a shell script that orchestrates each step in the process. 

## Install
Just clone this repo, the stream will handle initialization and installation of the datastream tools.

## Run it
```
/ngen-datastream/scripts/stream.sh ./configs/conf_datastream.json
```

## Formatting `conf_datastream.json`
### globals
| Field             | Description              | Required |
|-------------------|--------------------------|------|
| start_time        | Start simulation time (YYYYMMDDHHMM) | :white_check_mark: |
| end_time          | End simulation time  (YYYYMMDDHHMM) | :white_check_mark: |
| data_dir          | Name used in constructing the parent directory of the datastream. Must not exist prior to datastream run | :white_check_mark: |
| resource_dir      | Folder name that contains the datastream resources. If not provided, datastream will create this folder with default options |  |
| relative_path     | Absolute path to be prepended to any other path given in configuration file |  |
| subset_id         | catchment id to subset. If not provided, the geopackage in the resource_dir will define the spatial domain in entirety | Required only if resource_dir is not given  |

### Example `conf_datastream.json`
```
{
    "globals" : {
        "start_date"   : "",
        "end_date"     : "",
        "data_dir"     : "ngen-datastream-test",
        "resource_dir" : "datastream-resources-dev",
        "relative_to"  : "/home/jlaser/code/CIROH/ngen-datastream/data"
        "subset_id"    : ""
    }
}
```

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
`datastream-configs/` holds the all the configuration files the datastream needs in order to run. Note! The datastream can modify `conf_datastream.json` and generate it's own internal configs. `datastream-configs/` is the first place to look to confirm that a datastream run has been executed according to the user's specifications. 
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
`datastream-resources/` holds the data files required to perform computations required by the datastream. The user can supply this directory by pointing the configuration file to `resource_dir`. If not given by the user, datastream will generate this folder with these [defaults](#resource_dir). 
│
├── conf_datastream.json
│
├── conf_forcingprocessor.json
|
├── conf_nwmurl.json
`ngen-run` follows the directory structure described [here](#nextgen-run-directory-structure)

### resource_dir
TODO: explain defualts used in automated build

### Useful Hacks
TODO: Daily

## NextGen Run Directory Structure
Running ngen requires building a standard run directory complete with the necessary files. The datastream constructs this automatically. Below is an explanation of the standard. Reference for discussion of the standard [here](https://github.com/CIROH-UA/NGIAB-CloudInfra/pull/17). 

An ngen run directory `ngen-run` is composed of three necessary subfolders `config, forcings, outputs` and an optional fourth subfolder `metadata`.

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
 
### Configuration directory 
`ngen-run/config/`
.
`realization.json` :
The realization file serves as the primary model configuration for the ngen framework. An example can be found [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/data/standard_run/config/realization.json). This file specifies which models/modules to run and with which parameters, run parameters like date and time, and hydrofabric specifications.

`catchments.geojson`, `nexus.geojson`,`crosswalk.json`, `flowpaths` ,`flowpath_edit_list.json` :
These files contain the [hydrofabric](https://mikejohnson51.github.io/hyAggregate/) (spatial data). An example can be found [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/data/standard_run/config/catchments.geojson). Tools to create these files can be found at [LynkerIntel's hfsubset](https://github.com/LynkerIntel/hfsubset).

Other files may be placed in this subdirectory that relate to internal-ngen-models/modules. It is common to define variables like soil parameters in these files for ngen modules to use.

## Versioning
The ngen framework uses a merkel tree hashing algorithm to version each ngen run. This means that the changes a user makes to any input files in `ngen-run` will be tracked and diff'd against previous input directories. While an explaination of how awesome this is can be found elsewhere, the important thing to know is the user must prepare a clean input directory (`ngen-run`) for each run they want to make. 

"Clean" means here that every file in the `ngen-run` is required for the immediate run the user intends to make. For instance, if the user creates a new realization configuration file, the old file must be removed before using `ngen-run` as an input directory to ngen. In other words, each configuration file type (realization, catchment, nexus, etc.) must be unique within `ngen-run`.
