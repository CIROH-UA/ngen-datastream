Below is the output of `./scripts/datastream -h`. A more in depth of each option is given in the table below. 

```
Usage: ./scripts/datastream [options]
Either provide a datastream configuration file
  -c, --CONF_FILE           <Path to datastream configuration file> 
or run with cli args
  -s, --START_DATE          <YYYYMMDDHHMM or "DAILY"> 
  -e, --END_DATE            <YYYYMMDDHHMM> 
  -C, --FORCING_SOURCE      <Forcing source option> 
  -d, --DATA_DIR            <Path to write to> 
  -R, --REALIZATION         <Path to realization file> 
  -g, --GEOPACKAGE          <Path to geopackage file> 
  -I, --SUBSET_ID           <Hydrofabric id to subset>  
  -i, --SUBSET_ID_TYPE      <Hydrofabric id type>  
  -v, --HYDROFABRIC_VERSION <Hydrofabric version> 
  -D, --DOMAIN_NAME         <Name for spatial domain> 
  -r, --RESOURCE_DIR        <Path to resource directory> 
  -f, --NWM_FORCINGS_DIR    <Path to nwm forcings directory> 
  -N, --NGEN_BMI_CONFS      <Path to ngen BMI config directory> 
  -F, --NGEN_FORCINGS       <Path to ngen forcings directory, tarball, or netcdf> 
  -S, --S3_BUCKET           <s3 bucket to write output to>  
  -o, --S3_PREFIX           <File prefix within s3 bucket> 
  -n, --NPROCS              <Process limit> 
  -y, --DRYRUN              <True to skip calculations> 
  -E, --EVAL                <True to run TEEHR evaluation service> 
  ```

### Explanation of cli args (or variables in defined in `CONF_FILE`)
| Field               | Flag | Description              | Required   |
|---------------------|------|--------------------|------|
| START_DATE          | `-s` |Start simulation time (YYYYMMDDHHMM) or "DAILY" | :white_check_mark: | |
| END_DATE            | `-e` |End simulation time  (YYYYMMDDHHMM) | :white_check_mark: |
| FORCING_SOURCE | `-C` |Select the forcings data provider. Format is `NWM_$VERSION_$RUN_TYPE_$INIT_CYCLE_$MEMBER` Options include NWM_RETRO_V2, NWM_RETRO_V3, NWM_V3_SHORT_RANGE_00, NWM_V3_MEDIUM_RANGE_00_0, NWM_V3_ANALYSIS_ASSIM_16, NWM_V3_ANALYSIS_ASSIM_EXTEND, NOMADS, NOMADS_POSTPROCESSED | :white_check_mark: |
| DATA_DIR           | `-d` |Absolute local path to construct the datastream run. | :white_check_mark: |
| REALIZATION         | `-R` |Path to NextGen realization file | Required here or file exists in `RESOURCE_DIR/config` |
| GEOPACKAGE          | `-g` | Path to hydrofabric, can be s3URI, URL, or local file. Generate file with [hfsubset](https://github.com/lynker-spatial/hfsubsetCLI) or use SUBSET args. | Required here or file exists in `RESOURCE_DIR/config` |
| SUBSET_ID_TYPE      | `-i` | id type corresponding to "id" [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option) | Required here if user is not providing GEOPACKAGE and GEOPACKAGE_ATTR. |
| SUBSET_ID           | `-I` | catchment id to subset [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option) | Required here if user is not providing GEOPACKAGE and GEOPACKAGE_ATTR.  |
| HYDROFABRIC_VERSION | `-v` |$\geq$ v20.1 [See hfsubset for options](https://github.com/LynkerIntel/hfsubset?tab=readme-ov-file#cli-option)  | Required here if user is not providing GEOPACKAGE and GEOPACKAGE_ATTR. | 
| DOMAIN_NAME         | `-D` | Name for spatial domain in run, stripped from gpkg if not supplied |  |
| RESOURCE_DIR       | `-r` |Path to directory that contains the datastream resources. More explanation [here](#resource_dir-datastream-resources). |  |
| NWM_FORCINGS_DIR | `-f` |Path to local directory containing nwm files. Alternatively, these file could be stored in RESOURCE_DIR as nwm-forcings. |  |
| NGEN_BMI_CONFS | `-N` |Path to local directory containing NextGen BMI configuration files. Alternatively, these files could be stored in RESOURCE_DIR under `config/`.  See here for [directory structure](#configuration-directory-ngen-runconfig). |  |
| NGEN_FORCINGS  | `-F` | Path to local ngen forcings directory holding ngen forcing csv's or parquet's. Also accepts tarball or netcdf. Alternatively, this file(s) could  be stored in RESOURCE_DIR at `ngen-forcings/`. |  |
| S3_BUCKET           | `-S` | AWS S3 Bucket to write output to |  |
| S3_PREFIX           | `-o` | Path within S3 bucket to write to |
| DRYRUN             | `-y` | Set to "True" to skip all compute steps. |
| NPROCS              | `-n` | Maximum number of processes to use in any step of  `ngen-datastream`. Defaults to `nprocs - 2` |  |
| CONF_FILE            | `-c` | Store CLI args as env variables in a file. |  |
| EVAL | `-E` | Set to "True" to run the TEEHR automated evaluation service on NextGen outputs. |  |

### Note for supplying file(s) paths
DataStreamCLI is designed to pick up files or folder whether they are local, public, or in AWS s3 object storage.

DataStreamCLI can accept local or non-local paths. The following are all allowed.
``` 
For file like paths (i.e. providing explicit geopackage path)
1. A local absolute (or relative) path : /home/user/data/nextgen_VPU_09.gpkg
2. A URL : https://ciroh-community-ngen-datastream.s3.us-east-1.amazonaws.com/v2.2_resources/VPU_09/config/nextgen_VPU_09.gpkg
3. A s3 URI: s3://ciroh-community-ngen-datastream/v2.2_resources/VPU_09/config/nextgen_VPU_09.gpkg

For folder like paths (i.e. providing a resource directory)
1. A local absolute (or relative) folder : /home/user/data/v2.2_resources/VPU_09
2. A s3 URI prefix : s3://ciroh-community-ngen-datastream/v2.2_resources/VPU_09
```

Note here that DataStreamCLI will treat a s3 URI prefix like a directory.

