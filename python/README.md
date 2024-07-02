# ngen-datastream python
Scripts to create ngen bmi module configuration files and validate ngen-run packages.

## `ngen_configs_gen.py`
Note: see [noahowp_pkl](#noahowp_pklpy) before running this script. Currently, the datastream creates the noahowp config files from a template config within the repository. 
The t-route config is also created from a template within this repository. Soon these will be generated with pydantic models within [ngen-cal](https://github.com/NOAA-OWP/ngen-cal)
```
usage: ngen_configs_gen.py [-h] [--hf_file HF_FILE] [--outdir OUTDIR]
                           [--pkl_file PKL_FILE] [--realization REALIZATION] 
options:
  -h, --help                 show this help message and exit
  --hf_file HF_FILE          Path to the .gpkg
  --outdir OUTDIR            Path to write ngen configs
  --pkl_file PKL_FILE        Path to the noahowp pkl
  --realization REALIZATION  Path to the ngen realization
```


## `noahowp_pkl.py`
Generate .pkl file read by `ngen_configs_gen.py`, from which noahowp configs will be generated for each catchment present in the attributes file.
```
usage: noahowp_pkl.py [-h] [--hf_lnk_file HF_LNK_FILE] [--outdir OUTDIR]
options:
  -h, --help                show this help message and exit
  --hf_lnk_file HF_LNK_FILE Path to the .gpkg attributes
  --outdir OUTDIR           Path to write ngen configs
```

## `configure-datastream.py`
Generates the three configuration files for the datastream. One each for the datastream itself, forcingprocessor, and nwmurl.
```
usage: configure-datastream.py [-h] [--docker_mount DOCKER_MOUNT] [--start_date START_DATE] [--end_date END_DATE] [--data_path DATA_PATH] [--gpkg GPKG] [--gpkg_attr GPKG_ATTR] [--resource_path RESOURCE_PATH]
                               [--subset_id_type SUBSET_ID_TYPE] [--subset_id SUBSET_ID] [--hydrofabric_version HYDROFABRIC_VERSION] [--nwmurl_file NWMURL_FILE] [--nprocs NPROCS] [--host_type HOST_TYPE]
                               [--domain_name DOMAIN_NAME]
options:
  -h, --help                                  show this help message and exit
  --docker_mount DOCKER_MOUNT                 Path to DATA_PATH mount within docker container
  --start_date START_DATE                     Set the start date
  --end_date END_DATE                         Set the end date
  --data_path DATA_PATH                       Set the data directory
  --gpkg GPKG                                 Path to geopackage file
  --resource_path RESOURCE_PATH               Set the resource directory
  --subset_id_type SUBSET_ID_TYPE             Set the subset ID type
  --subset_id SUBSET_ID                       Set the subset ID
  --hydrofabric_version HYDROFABRIC_VERSION   Set the Hydrofabric version
  --nwmurl_file NWMURL_FILE                   Provide an optional nwmurl file
  --nprocs NPROCS                             Maximum number of processes to use
  --host_type HOST_TYPE                       Type of host
  --domain_name DOMAIN_NAME                   Name of spatial domain
```

## `run_validator.py`
Validates a ngen-run package. More specifically the following criteria must be met:

1) Standard ngen-run directory formatting. See [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/README.md#ngen-run) for more on the ngen-run folder.
2) A single geopackage exists
3) A single realization file exists
4) A forcing file is found at the path supplied in the realization for each catchment found in the geopackage.
5) A configuration file is found at the bmi module config path supplied in the realization for each catchment found in the geopackage.

```
usage: run_validator.py [-h] [--data_dir DATA_DIR] [--tarball TARBALL]

options:
  -h, --help           show this help message and exit
  --data_dir DATA_DIR  Path to the ngen input data folder
  --tarball TARBALL    Path to tarball to be validated as ngen input data folder
```
