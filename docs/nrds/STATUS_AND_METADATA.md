# Status
Last updated: 08/2025

Changes
* Processing has scaled back to only regions with community contributed parameters (VPU16 as of now)
* Implemented all forecast cycles for medium range
* Metadata improvements detailed in the latest release https://github.com/CIROH-UA/ngen-datastream/releases/tag/v1.0.1 .

Status 
* Only VPU16 running
* Run Types - short_range (all init cycles), medium_range (all init cycles, 1st member), analysis_assim_extend
* Cold start
* v2.2 hydrofabric

Future Updates
* Implement community contribution workflow as detailed in issue https://github.com/CIROH-UA/ngen-datastream/issues/170
* Implement warm state
* Update to latest hydrofabric when released.

# Status
Last updated: 05/2025

Status
* Spatial distribution of processing - split by VPU and subsetted manually from v2.2 [CONUS](https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/v2.2/conus/conus_nextgen.gpkg). 
* VPUs available : 02, 03N, 03S, 03W, 04, 05, 06, 08, 09, 10L, 10U, 11, 12, 13, 14, 15, 16, 18
  * (05, 10L, 10U, 11 not available for medium range)
* Run Types - short_range (all init cycles), medium_range (00 init cycle, 1st member), analysis_assim_extend
* Cold start
* NextGen configuration - NOAH-OWP, PET, CFE, and troute. Dynamically read on each execution from [publicly available realizations](https://datastream.ciroh.org/index.html#realizations/) that now hold [mutable community parameters](https://datastream.ciroh.org/index.html#parameters/).

Planned Updates From Last Update (02/2025)
* (DONE!) Begin integrated community proposed edits to NextGen configuration 
* (DONE!) Implement routing
* (DONE!) Expand to additional VPUs
* (None released since last update) Remain up to date with the latest hydrofabric release
* (TODO) Avoid manual subsetting of hydrofabric and rely on OWP tooling ([hfsubset](https://github.com/owp-spatial/hfsubsetCLI)) instead

Planned Updates
* Remain up to date with the latest hydrofabric release
* add VPUs 01, 07, 17
* Implement all medium_range members at all init cycles
* Codify a workflow by which community members may propose edits to the [official parameters set](https://datastream.ciroh.org/index.html#parameters/)
* Evaluate predictive performance on a national scale 

---------
## Previous Updates

Updated: 02/2025

Status
* Hydrofabric Version - v2.2
* Spatial distribution of processing - split by VPU and subsetted manually from v2.2 [CONUS](https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/v2.2/conus/conus_nextgen.gpkg). 
* VPUs available : 02, 03W, 16
* Run Types - short_range (00 init cycle), medium_range (00 init cycle, 1st member), analysis_assim_extend
* Cold start
* NextGen configuration - NOAH-OWP, PET, CFE template for all of [CONUS](https://github.com/CIROH-UA/ngen-datastream/tree/main/research_datastream/configuration/CONUS)
* Executions - Link [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/research_datastream/terraform_community/executions)

Planned Updates
* Begin integrated community proposed edits to NextGen configuration
* Implement routing
* Expand to additional VPUs
* Remain up to date with the latest hydrofabric release
* Avoid manual subsetting of hydrofabric and rely on OWP tooling ([hfsubset](https://github.com/owp-spatial/hfsubsetCLI)) instead

------
# Metadata
The metadata stored during a research datastream execution ensures transparency and thereby reproducibility. The research datastream metadata includes the standard [datastream metadata](https://github.com/CIROH-UA/ngen-datastream/blob/main/docs/STANDARD_DIRECTORIES.md#datastream-metadata) which is normally generated in any execution. The difference for the research datastream comes with the additional execution.json file that is used to start the AWS state machine. This file is described in the documentation [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/research_datastream/terraform/GETTING_STARTED.md#3-configure-execution-file).
