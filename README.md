# Data Access
Running ngen requires building a standard run directory complete with the necessary files. Below is an explanation of the standard and an example that can be found [here](https://github.com/CIROH-UA/ngen-datastream/tree/forcingprocessor/data/standard_run) Reference for discussion of the standard here: https://github.com/CIROH-UA/NGIAB-CloudInfra/pull/17 . 

An ngen run directory (`data_dir`) is composed of three necessary subfolders (`config, forcings, outputs`). `data_dir` may have any name, but the subfolders must follow this naming convention. 

```
data_dir/
│
├── config/
│
├── forcings/
│
├── outputs/
```

The `data_dir` directory contains the following subfolders:

- `config`: Holds model configuration files and hydrofabric configuration files. A deeper explanation [here]()

- `forcings`: The `forcings` folder is where external data or input files for the system are stored.

- `outputs`: All the output files and results of the system are saved in the `outputs` directory.

## Versioning
The ngen framework uses a merkel tree hashing algorithm to version each ngen run. This means that the changes a user makes to any input files in `data_dir` will be tracked. While an explaination of how awesome this is can be found elsewhere, the important thing to know is the user must prepare a clean input directory (`data_dir`) for each run they want to make. 

"Clean" means here that every file in the `data_dir` is required for the immediate run the user intends to make. For instance, if the user creates a new realization configuration file, the old file must be removed before using `data_dir` as an input directory to ngen. In other words, each configuration file type (realization, catchment, nexus, etc.) must be unique within `data_dir`.

## Configuration directory 
`/data_dir/config/`

`realization.json` :
The realizations file serves as the primary model configuration for the ngen framework. An example can be found [here](https://github.com/CIROH-UA/ngen-datastream/tree/forcingprocessor/data/standard_run/config/realization.json). This file specifies which models to run and with which parameters, run parameters like date and time, and hydrofabric specifications.

`catchments.geojson`, `nexus.geojson`,`crosswalk.json`, `flowpaths` ,`flowpath_edit_list.json` :
These files contain the [hydrofabric](https://mikejohnson51.github.io/hyAggregate/) (spatial data). An example can be found [here](https://github.com/CIROH-UA/ngen-datastream/tree/forcingprocessor/data/standard_run/config/catchments.json)