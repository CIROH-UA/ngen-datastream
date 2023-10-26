# Data Access
Running ngen requires building a standard run directory complete with the necessary files. Below is an explanation of the standard and an example that can be found [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/data/standard_run) Reference for discussion of the standard [here](https://github.com/CIROH-UA/NGIAB-CloudInfra/pull/17). 

An ngen run directory `data_dir` is composed of three necessary subfolders `config, forcings, outputs` and an optional fourth subfolder `metadata`. `data_dir` may have any name, but the subfolders must follow this naming convention. 

```
data_dir/
│
├── config/
│
├── forcings/
|
├── metadata/
│
├── outputs/
```

The `data_dir` directory contains the following subfolders:

- `config`:  model configuration files and hydrofabric configuration files. A deeper explanation [here](#Configuration-directory)
- `forcings`: catchment-level forcing timeseries files. These can be generated with the [forcingprocessor](https://github.com/CIROH-UA/ngen-datastream/tree/main/forcingprocessor). Forcing files contain variables like wind speed, temperature, precipitation, and solar radiation.
- `metadata` is an optional subfolder. This is programmatically generated and it used within to ngen. Do not edit this folder.
- `outputs`: This is where ngen will place the output files.
 
### Configuration directory 
`data_dir/config/`
.
`realization.json` :
The realization file serves as the primary model configuration for the ngen framework. An example can be found [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/data/standard_run/config/realization.json). This file specifies which models/modules to run and with which parameters, run parameters like date and time, and hydrofabric specifications.

`catchments.geojson`, `nexus.geojson`,`crosswalk.json`, `flowpaths` ,`flowpath_edit_list.json` :
These files contain the [hydrofabric](https://mikejohnson51.github.io/hyAggregate/) (spatial data). An example can be found [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/data/standard_run/config/catchments.geojson). Tools to create these files can be found [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/subsetting).

Other files may be placed in this subdirectory that relate to internal-ngen-models/modules. It is common to define variables like soil parameters in these files for ngen modules to use.

## Versioning
The ngen framework uses a merkel tree hashing algorithm to version each ngen run. This means that the changes a user makes to any input files in `data_dir` will be tracked and diff'd against previous input directories. While an explaination of how awesome this is can be found elsewhere, the important thing to know is the user must prepare a clean input directory (`data_dir`) for each run they want to make. 

"Clean" means here that every file in the `data_dir` is required for the immediate run the user intends to make. For instance, if the user creates a new realization configuration file, the old file must be removed before using `data_dir` as an input directory to ngen. In other words, each configuration file type (realization, catchment, nexus, etc.) must be unique within `data_dir`.




