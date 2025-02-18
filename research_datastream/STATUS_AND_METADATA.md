# Status
Last updated: 02/2025

The current status of the research datastream is explained below
* Hydrofabric Version - v2.2
* Spatial distribution of processing - split by VPU and subsetted manually from v2.2 [CONUS](https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/v2.2/conus/conus_nextgen.gpkg). 
* VPUs available : 02, 03W, 16
* Run Types - short_range, medium_range, analysis_assim_extend
* NextGen configuration - NOAH-OWP, PET, CFE template for all of [CONUS](https://github.com/CIROH-UA/ngen-datastream/tree/main/research_datastream/configuration/CONUS)
* Executions - Link [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/research_datastream/terraform_community/executions)

# Planned Updates
* Begin integrated community proposed edits to NextGen configuration
* Implement routing
* Expand to additional VPUs
* Remain up to date with the latest hydrofabric release
* Avoid manual subsetting of hydrofabric and rely on OWP tooling ([hfsubset](https://github.com/owp-spatial/hfsubsetCLI)) instead


# Metadata
The metadata stored during a research datastream execution ensures transparency and thereby reproducibility. The research datastream metadata includes the standard [DataStreamCLI metadata](https://github.com/CIROH-UA/ngen-datastream/blob/main/docs/STANDARD_DIRECTORIES.md#datastream-metadata) which is normally generated in any execution. The difference for the research datastream comes with the additional execution.json file that is used to start the AWS state machine. This file is described in the documentation [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/research_datastream/terraform/GETTING_STARTED.md#3-configure-execution-file).