# Updating an Existing Datastream

The sections below describe the parts of a running datastream that are open to change and where each one is handled.

---

## Calibrated Parameters

The NRDS configures its simulations with the NextGen realization file. By default it calculates model parameters from the hydrofabric, which means **the parameters currently running are largely uncalibrated**.

Community contributed parameters are used in the next and all executions following updating of the public realization files in AWS s3 storage. Proposing and accepting are decoupled steps, so submitting has no effect on the running system until the parameters are accepted.

### Submitting

Open a [Contribute Calibrated Parameters](https://github.com/CIROH-UA/ngen-datastream/issues/new?template=parameter_contribution.yml) issue with the package URL. The template also asks how the parameters were produced: the calibration method, the observations and period, the objective function, and how the result compares to the uncalibrated defaults.

Write that part at length. The NRDS neither calibrates nor adjudicates calibration methodology, so what it needs is the parameters, their provenance, and enough context for the next contributor to build on your work.

### Contributions covering several gages

Calibrating several gages in one experiment may leave the researcher with a geopackage and a realization per gage. Submit them as one package and one issue, with a directory per gage holding that gage's files. The [Contribute Calibrated Parameters](https://github.com/CIROH-UA/ngen-datastream/issues/new?template=parameter_contribution.yml) template shows the layout and asks for per-gage performance.

### A note on overlapping submissions

Parameters for the same catchments may arrive from more than one contributor. Where submissions overlap, accepting one set replaces the other, and the reasoning belongs in the open on the relevant issues. Systematic evaluation against observations is the eventual basis for these decisions, and community input on standards and metrics is welcome.

---

## Realization Files

The realization file specifies which [BMI](https://doi.org/10.21105/joss.02317)-compliant model components execute in each catchment, how variables are mapped between them, and what runtime parameters apply. Switching a datastream from one formulation to another is accomplished by swapping the realization file referenced in the execution specification, with no infrastructure change.

Use the [Propose a Datastream Update](https://github.com/CIROH-UA/ngen-datastream/issues/new?template=update_datastream.yml) template. Contributions here include reconfigured variable mappings, adjusted runtime parameters, and mosaic configurations that apply different formulations across different parts of a domain. NextGen supports heterogeneous mosaic formulations within a single realization. No deployed NRDS datastream exercises this, and the case for diagnostic model selection across CONUS is made in [Johnson (2023)](https://doi.org/10.1029/2023JD038534). A well-motivated mosaic configuration would be a novel contribution.

---

## Forcing Processing

[CIROH-UA/forcingprocessor](https://github.com/CIROH-UA/forcingprocessor)

NextGen operates on catchments, so it requires forcings as catchment-averaged time series rather than gridded fields. Operational atmospheric models produce gridded data. The Forcing Processor bridges that gap: it reads gridded forcing files, computes area-weighted averages over each catchment polygon, and writes the result in NextGen-compatible format.

It runs as its own scheduled datastream over CONUS, feeding every simulation datastream in the system. It is a standalone containerized project, so it can be developed and tested independently of the NRDS deployment.

Because forcing preparation in the NRDS is model-agnostic and supplies several datastreams with input, improvements affect those downstream. 

Changes here are code contributions: the code that processes a product is what makes it available to the system. Ideas without code are welcome as a [suggestion issue](https://github.com/CIROH-UA/ngen-datastream/issues/new?template=suggestion.yml), where they sit on the record as a demand signal.

Changes that land here include support for new forcing sources, handling for different temporal or spatial resolutions, and alternative approaches to weight generation and catchment averaging. See [Contribution Ideas](CONTRIBUTING.md#contribution-ideas).

### Output format and efficiency

The Forcing Processor writes NextGen-compatible forcing files consumed by every downstream datastream. Contributions to serialization efficiency, compression, chunking, and precision trade-offs reduce both storage cost and the I/O time of every simulation that reads them. Options are under discussion in [forcingprocessor #62](https://github.com/CIROH-UA/forcingprocessor/discussions/62).

---

## Execution Metadata

[CIROH-UA/datastreamcli](https://github.com/CIROH-UA/datastreamcli) · [open an issue](https://github.com/CIROH-UA/datastreamcli/issues/new?template=metadata_request.yml)

Every execution writes a metadata bundle: the execution specification, container image hashes, the input file inventory, and the command history. This record is what makes an NRDS output reproducible, since a researcher can pull the exact containers and inputs it references and reconstitute the run.

What is captured today is documented in [STANDARD_DIRECTORIES.md](https://github.com/CIROH-UA/datastreamcli/blob/main/docs/STANDARD_DIRECTORIES.md), which walks through `datastream-metadata/` field by field. Read that before asking for something new, since it may already be there. Output layout in the public bucket is described in the [NRDS S3 documentation](https://ciroh-community-ngen-datastream.s3.amazonaws.com/README.html).

**The current schema reflects what the development team judged useful, which is a guess about community needs.**

If you consume NRDS outputs and there is provenance information you need that we are not tracking, tell us. This costs you three fields and no code. Schema additions are cheap now and expensive to retrofit once years of output carry the old shape.

---

## Model Versions in NGIAB

[CIROH-UA/NGIAB-CloudInfra](https://github.com/CIROH-UA/NGIAB-CloudInfra) · [docs](https://github.com/CIROH-UA/NGIAB-CloudInfra/tree/main/docs)

NRDS simulations run in the maintained `awiciroh/ciroh-ngen-image` container, which we refer to as NGIAB ([Patel et al., 2025](https://doi.org/10.1016/j.envsoft.2025.106666)). Each datastream pins a semver tag of that image, so the model code running in production is whatever the pinned tag contains.

If you maintain a model already in NGIAB and have improved it, the change reaches the NRDS in two steps. The improvement goes into the NGIAB build and ships in a new tagged image, then the datastreams using it move to that tag. Open a [Propose a Datastream Update](https://github.com/CIROH-UA/ngen-datastream/issues/new?template=update_datastream.yml) issue naming the new tag, what changed in the model, and which datastreams should pick it up.

Running two versions side by side is also possible, since a second datastream pinned to a different image tag makes the difference between model versions measurable at continental scale.

Getting a model into NGIAB for the first time is a separate path. See [NEW_DATASTREAM.md](NEW_DATASTREAM.md).

---

## Hydrofabric

The hydrofabric is the spatial substrate of every NextGen simulation: catchment polygons, nexus locations, and the connectivity defining how water moves between them. The NRDS currently runs on Lynker Spatial hydrofabric v2.2, and the version is recorded in the execution metadata of every simulation.

The hydrofabric evolves, in both the software and the physical sense. Different versions imply different catchment definitions, different drainage areas, and therefore different model behavior, and the landscape itself changes through storms and human infrastructure. Each release improves on the last. The NRDS tracks new versions, which makes it a natural venue for demonstrating what a hydrofabric update does to continental-scale simulation output.

**Hydrofabric contributions are made upstream**, and the NRDS inherits them:

- **[lynker-spatial/community.fabric](https://github.com/lynker-spatial/community.fabric)** is the path for changes intended for long-term inclusion in the NextGen hydrofabric. Structured issue templates cover geometry corrections, coordinate fixes, and proposals to integrate new datasets. Reports should reference the reference fabric identifiers.
- **[CIROH-UA/community_hf_patcher](https://github.com/CIROH-UA/community_hf_patcher)** is the CIROH Community Hydrofabric, a fork of v2.2 carrying patches that improve compatibility with CIROH projects, pending hydrofabric v3.

A hydrofabric version change carries work on the NRDS side. Model configurations are derived per hydrofabric version and are regenerated with each release, and contributed parameters apply to the version they were calibrated against. This is why parameter submissions state their hydrofabric version.

---

