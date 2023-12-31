# Docker commands
This directory holds Dockerfiles to create containers for each component of the datastream. Below are example commands to utilize these containers individually.

# Subsetting (hfsubset)
```
docker build /ngen-datastream/docker/hfsubsetter –t hfsubsetter –no-cache
docker run -it --rm -v /path/to/your-directory:/mounted_dir hfsubsetter ./hfsubset -o ./mounted_dir/catchment-101subset.gpkg -r "v20" -t comid "101"
```

# ForcingProcessor
```
docker build /ngen-datastream/docker/forcingprocessor -t forcingprocessor --no-cache
docker run -it --rm -v /ngen-datastream:/mounted_dir forcingprocessor python /ngen-datastream/forcingprocessor/src/forcingprocessor/forcingprocessor.py /mounted_dir/forcingprocessor/configs/conf_docker.json
```
Note that both the filenamelist.txt and weights.json file must be generated first and paths properly set in the config. 

# Validator
```
docker build /ngen-datastream/docker/validator -t validator --no-cache
docker run -it --rm -v /ngen-datastream:/mounted_dir validator python /ngen-cal/python/run_validator.py --data_dir /mounted_dir/data/standard_run
```