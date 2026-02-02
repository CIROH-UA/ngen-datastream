# Status
Last Updated: 02/2026

Changes
* A Routing-only datastream has been added! This datastream inputs National Water Model v3 pre-reouting outputs (`q_lateral`), remaps them to the NextGen v2.2 hydrofabric, and then fed into t-route. 
* All datastream forcings and output data from the original `v2.1`, `v2.2` prefixes have been moved to `forcings/v2.2_hydrofabric` and `outputs/cfe_nom/v2.2_hydrofabric`, respectively. Prefixes `v2.1`, `v2.2` no longer exist.

Status Routing-Only DataStream (DEV)
* Output data exists at `outputs/routing_only/v2.2_hydrofabric/...`
* Does not input NextGen forcings. Inputs National Water Model v3 pre-routing outputs, `q_lateral`.
* VPU 03W only
* Run Types - short_range (hourly, every hour)
* v2.2 hydrofabric

Status LSTM DataStream (DEV)
No changes from last update
* Output data exists at `outputs/lstm/v2.2_hydrofabric/...`
* Forcings from `forcings/v2.2_hydrofabric`
* VPU 09 only
* Run Types - short_range (hourly, every hour), medium_range (4 times per day, every 6 hours, first member), analysis_assim_extend(once per day at 16z)
* Cold start
* v2.2 hydrofabric

Status CFE NOM DataStream
No changes from last update
* Output data exists at `outputs/cfe_nom/v2.2_hydrofabric/...`
* Forcings from `forcings/v2.2_hydrofabric`
* All VPUs
* Run Types - short_range (hourly, every hour), medium_range (4 times per day, every 6 hours, first member), analysis_assim_extend(once per day at 16z)
* Cold start
* v2.2 hydrofabric

---
Updated: 11/2025

Changes
* All datastream output data is now being written to the prefix `outputs/<DATASTREAM_NAME>/v2.2_hydrofabric/ngen.<DATE>/<RUN_TYPE>/<INIT>/<VPU>`
* The troute file has been separated from the tar file and exists at the additional prefix of `ngen-run/outputs/troute/*.nc`
* A development lstm datastream has been deployed with this [NextGen Rust-base LSTM realization.](https://ciroh-community-ngen-datastream.s3.amazonaws.com/realizations/realization_rust_lstm_troute.json) 

Status LSTM DataStream (DEV)
* Output data exists at `outputs/lstm/v2.2_hydrofabric/...`
* VPU 09 only
* Run Types - short_range (all init cycles), medium_range (all init cycles, first member), analysis_assim_extend
* Cold start
* v2.2 hydrofabric

Status CFE NOM DataStream
* Output data exists at `outputs/cfe_nom/v2.2_hydrofabric/...`
* All VPUs
* Run Types - short_range (all init cycles), medium_range (all init cycles, first member), analysis_assim_extend
* Cold start
* v2.2 hydrofabric
  
---
Updated: 10/2025

Changes
* On October 14th, the NRDS scaled back by turning off all medium range members besides the first.

Status
* All VPUs
* Run Types - short_range (all init cycles), medium_range (all init cycles, first member), analysis_assim_extend
* Cold start
* v2.2 hydrofabric

---
Updated: 09/2025

Changes
* On September 1st, the NRDS scaled out to full conus simulation with a NextGen configuration of NOM, CFE, and troute.
* Lagged forcings medium range ensembling implemented

Status
* All VPUs
* Run Types - short_range (all init cycles), medium_range (all init cycles, all members), analysis_assim_extend
* Cold start
* v2.2 hydrofabric

---
Updated: 08/2025

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

---
Updated: 05/2025

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

---
Updated: 02/2025

Status
* Hydrofabric Version - v2.2
* Spatial distribution of processing - split by VPU and subsetted manually from v2.2 [CONUS](https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/v2.2/conus/conus_nextgen.gpkg). 
* VPUs available : 02, 03W, 16
* Run Types - short_range (00 init cycle), medium_range (00 init cycle, 1st member), analysis_assim_extend
* Cold start
* NextGen configuration - NOAH-OWP, PET, CFE template for all of [CONUS](https://github.com/CIROH-UA/ngen-datastream/tree/main/research_datastream/configuration/CONUS)
* Executions - Link [here](https://github.com/CIROH-UA/ngen-datastream/tree/main/infra/aws/terraform/modules/schedules/executions)

Planned Updates
* Begin integrated community proposed edits to NextGen configuration
* Implement routing
* Expand to additional VPUs
* Remain up to date with the latest hydrofabric release
* Avoid manual subsetting of hydrofabric and rely on OWP tooling ([hfsubset](https://github.com/owp-spatial/hfsubsetCLI)) instead

------
# Metadata
The metadata stored during a research datastream execution ensures transparency and thereby reproducibility. The research datastream metadata includes the standard [datastream metadata](https://github.com/CIROH-UA/ngen-datastream/blob/main/docs/STANDARD_DIRECTORIES.md#datastream-metadata) which is normally generated in any execution. The difference for the research datastream comes with the additional execution.json file that is used to start the AWS state machine. This file is described in the documentation [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/infra/aws/terraform/docs/GETTING_STARTED.md#3-configure-execution-file).
