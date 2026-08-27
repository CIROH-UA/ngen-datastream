# NextGen Research DataStream: Community Contributions

The NextGen Research DataStream (NRDS) executes community hydrologic modeling methods at continental scale, on an operational cadence, with all inputs, outputs, code, and execution metadata publicly available. It is the first system to continuously execute the NextGen Prototype, the model engine that will drive NWM4.0, across the United States.

Six datastreams run today, spanning process-based and machine learning streamflow prediction, forcing preparation, and channel routing. See the [datastream catalog](../DATASTREAMS.md) for a detailed description of existing deployments.

The documentation in this folder serves to provide community members with clear guidance on why and how to make a contribution to the NRDS system.

---

## Start Where You Are

| Read this | If you want to |
|---|---|
| **[BACKGROUND.md](BACKGROUND.md)** | Understand what the NRDS is, why it exists, what a datastream is, and where the system stops |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | See the two contribution paths, which issue template to use, and what to know before opening an issue |
| **[NEW_DATASTREAM.md](NEW_DATASTREAM.md)** | Propose a new scheduled datastream: a model formulation, downstream application, retrospective, or ensemble configuration |
| **[UPDATE_DATASTREAM.md](UPDATE_DATASTREAM.md)** | Improve something already running: calibrated parameters, processing code, forcing capabilities, or input data |

---

## Repositories and Tools

| Repository | Role |
|---|---|
| [ngen-datastream](https://github.com/CIROH-UA/ngen-datastream) | NRDS infrastructure and datastream execution specifications |
| [datastreamcli](https://github.com/CIROH-UA/datastreamcli) | End-to-end NextGen simulation workflow for a single datastream run |
| [forcingprocessor](https://github.com/CIROH-UA/forcingprocessor) | Gridded forcing data to catchment-averaged NextGen forcings |
| [NGIAB-CloudInfra](https://github.com/CIROH-UA/NGIAB-CloudInfra) | The `awiciroh/ciroh-ngen-image` container in which NextGen simulations run |
| [NGIAB Data Preprocessor](https://github.com/CIROH-UA/NGIAB_data_preprocess) | Hydrofabric subsetting, including by USGS gage, and archived forcing retrieval |
| [ngen-cal](https://github.com/NOAA-OWP/ngen-cal) | NextGen calibration toolkit |
| [TEEHR](https://github.com/RTIInternational/teehr) | Evaluation framework; TEEHR-Cloud ingests public NRDS outputs |
| [community.fabric](https://github.com/lynker-spatial/community.fabric) | Hydrofabric corrections and additions |
| [community_hf_patcher](https://github.com/CIROH-UA/community_hf_patcher) | CIROH Community Hydrofabric patches |

Unsure where a contribution belongs? Open an issue in [ngen-datastream](https://github.com/CIROH-UA/ngen-datastream/issues/new/choose) and we will route it.

---
