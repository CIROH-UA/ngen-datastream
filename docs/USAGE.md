# Usage Guide
This document provides users with an introduction to running `ngen-datastream`. 

## Hardware
`ngen-datastream` is a powerful tool designed to utilize compute resources to their maximum extent. While it is possible to run `ngen-datastream` locally, it is often the case that NextGen runs are large enough that running on a dedicated host will be desired. Why?

Firstly, we have to acknowledge the memory required to hold a run of a certain size. For instance, forcingprocessor will create a single data cube of 4 byte elements which has dimensions ncatchments x time x nvar. Without going into the weeds, this example should show that, in general, the memory load of a `ngen-datastream` run will increase with both time and the number of catchments. This means that regardless of the host you're running `ngen-datastream` on, it is possible to request a run large enough (in time or space) to run out of memory.

Another factor to consider before executing is the maxmimum number of processes to allow. Unless you throttle `ngen-datastream` with the `-n` argument, the system will default to (nprocs_host - 2). For dedicated hosts, this is safe and you can even set `-n` to nprocs_host to maximize compute usage. However, if the user intends to deploy `ngen-datastream` on a non-dedicated host (one which has other programs running), they must be careful not to request too many processes. 

The last factor to consider is the NextGen configuration via the realization file. The NextGen framework allows users to select bmi modules to run in their simulation. More complex modules will lead to longer run times and larger memory requirements. 

All of these factors influence runtime. Larger complex runs with less resources will take longer to complete. To give the user an example of runtime, a complete datastream run for a day (24 time steps) over VPU 09 (11,000 catchments) should take about 5 minutes on an AWS t4g.2xlarge ec2 instance (8 processes on 8vCPU, 32GB, ARM) with CFE, PET, SLOTH, and NOM NextGen configuration.

## Software
In general, `ngen-datastream` will create all of the required NextGen input files for you. However, the imense configurability of the NextGen framework allows `ngen-datastream` to be executed in a plethora of ways, each of which may have their own unique compute, memory, or bandwidth constraints. With this in mind, `ngen-datastream` allows the user to provide their own input files. To make this specific, if a user wishes to use a different forcing processing alogrithm, it is possible to provide `ngen-datastream` with your own forcing.tar.gz file. Same with ngen bmi module configs. `ngen-datastream` will create these files for you, or you can supply your own with ngen-bmi-configs.tar.gz. The hope is that `ngen-datastream` is "batteries included", while not being dogmatic about exactly how to perform the compute.

## Other Considerations
These are not hard contraints, but rather should provide the user with a rough idea on how to run `ngen-datastream` safely given the configuration of the requested run and the hardware available. If a crash is experienced, increase memory resources or decrease either the size of the run or the number of processes.

Assuming the user is running over a domain of 10,000 catchments
1) For runs with simulation duration of days to weeks (months to year), each process should have access to around 1 (4) GB of RAM. For example, 8 processes would need access to 8 (32) GB RAM.
2) The ratio of runtime minutes to simulation time steps is ~1:10. In other words, a simulation with 24 hourly time steps should a few minutes to complete. This ratio will vary with hardware and run configuration.