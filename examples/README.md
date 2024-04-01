# Examples
Below are a few different ways to run the datastream. 

## First Run
For a user's first time running ngen-datastream over a spatial domain, run with cli args and no resource directory.:
```
./ngen-datastream/scripts/stream.sh \
-s DAILY \
-R https://github.com/CIROH-UA/ngen-datastream/raw/main/configs/ngen/realization_cfe_sloth_nom.json \
-g https://lynker-spatial.s3.amazonaws.com/v20.1/gpkg/nextgen_09.gpkg \
-G https://lynker-spatial.s3.amazonaws.com/v20.1/model_attributes/nextgen_09.parquet \
-n 8 \
-d /home/ec2-user/test
```
This command will execute ngen-datastream over VPU_09 with 24 hrs of forcings from today's date. The output will exist at `/home/ec2-user/test` with the reusable resource directory here `/home/ec2-user/test/datastream-resources`

## Repeated runs
Now that the user has a resource directory made for VPU_09, repeated runs can be made by just providing the resource directory.

First, copy the resource directory from the previous run:
```
cp -r /home/ec2-user/test/datastream-resources /home/ec2-user/resources_VPU09
```
Then re-run ngen-datastream with the resource directory and a new data path to write out to. Now the user can make changes to the realization file and repeat the run, without re-generating input files. This is referred to running in "lite" mode.
```
./ngen-datastream/scripts/stream.sh \
-s DAILY \
-r /home/ec2-user/resources_VPU09 \
-d /home/ec2-user/test2
```
## Need help?
If you're having trouble running ngen-datastream, reach out to Jordan (jlaser@lynker.com) or raise an issue in the repo.