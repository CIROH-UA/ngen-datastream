# Contributing to the NRDS

[BACKGROUND.md](BACKGROUND.md) covers what the NRDS is and where it stops. This page covers how to make a contribution to the system.

---

## Two Paths

### [New Datastreams](NEW_DATASTREAM.md)

Adding a new scheduled pipeline: a model formulation, an alternative forcing pipeline, a post-processing step, or an ensemble configuration.

A new datastream scales up system compute, consuming EC2 hours on every cycle and writing output to S3 for as long as it is retained. That recurring cost is the primary consideration in evaluating a proposal.

### [Updates to Existing Datastreams](UPDATE_DATASTREAM.md)

Changes to the tooling, code, configuration, or input data already in use: calibrated parameters, realization files, model code, forcing pipeline capabilities, hydrofabric updates.

An update may or may not affect compute. A parameter swap costs nothing extra. A more expensive forcing algorithm applied across CONUS does.

---

## Issue Templates

Every contribution starts with an issue.

| Template                                                                                                                              | Use it for                                                                                                  | Repository       |
| ------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ---------------- |
| [Contribute Calibrated Parameters](https://github.com/CIROH-UA/ngen-datastream/issues/new?template=parameter_contribution.yml)        | Calibrated parameters for a deployed formulation, submitted as a data package                               | ngen-datastream  |
| [Propose a New Datastream](https://github.com/CIROH-UA/ngen-datastream/issues/new?template=new_datastream.yml)                        | Any new scheduled pipeline, whether or not it simulates with NextGen                                        | ngen-datastream  |
| [Propose a Datastream Update](https://github.com/CIROH-UA/ngen-datastream/issues/new?template=update_datastream.yml)                  | Realization files, new model code, hydrofabric-related changes                                              | ngen-datastream  |
| [Propose a Forcing Processor Contribution](https://github.com/CIROH-UA/forcingprocessor/issues/new?template=forcing_contribution.yml) | New forcing sources, weight generation, averaging algorithms, output efficiency                             | forcingprocessor |
| [Request Execution Metadata](https://github.com/CIROH-UA/datastreamcli/issues/new?template=metadata_request.yml)                      | Provenance information you need in NRDS outputs but cannot find                                             | datastreamcli    |
| [Suggest an Idea](https://github.com/CIROH-UA/ngen-datastream/issues/new?template=suggestion.yml)                                     | Something the NRDS should do that you are not in a position to contribute                                   | ngen-datastream  |
| [Model Integration Checklist](https://github.com/CIROH-UA/NGIAB-CloudInfra/issues/new?template=model_integration_request.yml)         | Getting a NextGen model built into the NGIAB container, a prerequisite for deploying it in a new datastream | NGIAB-CloudInfra |

Hydrofabric corrections go to [community.fabric](https://github.com/lynker-spatial/community.fabric/issues).

---

## Things to Keep in Mind

**Write for the people who come after you.** Every issue and discussion here is public and is a source of knowledge for future researchers engaging with the system. Outside of future papers, these threads are the best description of what the system does and the clearest guide for the next contributor. Explain your reasoning, the science behind the contribution, and any existing issues you might be aware of. The [δHBV 2.0 integration issue](https://github.com/CIROH-UA/ngen-datastream/issues/337) shows the depth worth aiming for when filling out the now existing issue templates. 

**Explain why the contribution is worth making.** What the change does, and what question it lets the community answer. In addition, comment on the processing requirements and time. The research value combined with resource cost is what lets it be weighed against everything else competing for the same budget and review time. Cheaper methods cover more domain, run at finer cadence, and leave room for other datastreams.

**Target a hydrofabric version.** Spatial geometry and model parameters derive from the hydrofabric and change with each release, so calibrated parameters apply to the version they were built on. As of August 2026, the NRDS runs on v2.2.


---

## Contribution Ideas

Ideas the development team would find valuable, grouped by the path each one takes. Contributions outside this list are equally welcome.

### Ideas for New Datastreams

Each of these adds a new scheduled pipeline. See [NEW_DATASTREAM.md](NEW_DATASTREAM.md).

#### New model formulations

Process-based and machine learning approaches beyond what is deployed today. LSTM approaches have shown competitive skill since [Kratzert et al. (2018)](https://doi.org/10.5194/hess-22-6005-2018), with continued development through [Nearing et al. (2024)](https://doi.org/10.1038/s41586-024-07145-1) and within NextGen specifically in [Frame et al. (2025)](https://doi.org/10.1111/1752-1688.70000). Process-based contributions are equally wanted.

#### Ensemble and probabilistic capability

The NRDS produces deterministic point forecasts. Ensemble output would align it with operational practice ([Demargne et al., 2014](https://doi.org/10.1175/BAMS-D-12-00081.1)) and support methods producing distributions. Ensemble realization files, forcing and initial-condition perturbation strategies, and member-management patterns are all open.

#### Post-processing datastreams

Statistical and machine learning post-processing of simulation output is well established for the NWM ([Frame et al., 2021](https://doi.org/10.1111/1752-1688.12964); [Naser Neisary et al., 2025](https://doi.org/10.1016/j.envsoft.2025.106459)) and composes naturally as a downstream datastream consuming an upstream one.

### Ideas for Updates to Existing Datastreams

Each of these changes something the NRDS already runs. See [UPDATE_DATASTREAM.md](UPDATE_DATASTREAM.md).

#### Calibrated parameters

The deployed configurations run parameters derived from the hydrofabric, which are uncalibrated. Note that skill scores depend heavily on the metric chosen ([Gupta et al., 2009](https://doi.org/10.1016/j.jhydrol.2009.08.003); [Clark et al., 2021](https://doi.org/10.1029/2020WR029001)), so state what you optimized and why.

#### Alternative catchment averaging and weight generation

Catchment weights are currently produced with [exactextract](https://github.com/isciences/exactextract), which computes exact fractional area coverage of each grid cell by each catchment polygon, and forcings are the area-weighted mean of the cells a catchment overlaps.

That aggregation flattens sub-catchment variability in precipitation and temperature, and the flattening matters most where response is most sensitive to it: mountainous terrain, convective precipitation, sharp elevation gradients. [Ducker et al. (2025)](https://ui.adsabs.harvard.edu/abs/2025AMS...10555890D/abstract) evaluate how regridding method choice propagates through grid-to-catchment conversion in the NextGen forcings engine, and it is the natural starting point for work here.

Approaches worth building:

- **Nearest-neighbor and interpolation-based schemes**, including inverse-distance and bilinear
- **Elevation-band weighting**, preserving orographic precipitation and lapse-rate effects
- **Sub-catchment downscaling**, giving finer-grained variation within a catchment

Include a characterization of how the resulting forcings differ from current behavior, which is what makes a new algorithm evaluable. Approaches tuned to one formulation's assumptions relax the model-agnostic character of forcing preparation, which is acceptable and worth stating, since the right structure may then be a separate upstream datastream.

#### Support for additional forcing sources

The Forcing Processor currently reads NWM operational gridded products. Each additional source becomes an axis of experimentation for every datastream in the system. A contribution here is a reader for the source format, the variable mapping to NextGen-expected fields, and the handling needed to produce compliant output.

Related: sources arriving at sub-hourly, three-hourly, or daily cadence need aggregation or disaggregation to align with the simulation timestep, and formulations with long warm-up requirements need extended-lookback handling. Grid geometries other than the current products need corresponding weight generation.

#### Output format and efficiency

Forcing output is read by every downstream datastream, so serialization format, compression, chunking, and precision trade-offs reduce both storage cost and the I/O time of every simulation that reads it. Options are under discussion in [forcingprocessor #62](https://github.com/CIROH-UA/forcingprocessor/discussions/62).

#### Execution metadata

Tell us what provenance information you need that we are not tracking. Check [STANDARD_DIRECTORIES.md](https://github.com/CIROH-UA/datastreamcli/blob/main/docs/STANDARD_DIRECTORIES.md) first.
