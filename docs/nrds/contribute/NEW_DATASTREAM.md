# Proposing a New Datastream

A new datastream is the largest unit of contribution, and the mechanism by which a novel method gets exercised continuously at continental scale under operational-like conditions.

---

## Two Types of Datastream

The path depends on whether your method simulates through the NextGen framework.

**NextGen simulating datastreams** run a model formulation inside the NextGen Prototype ([Ogden et al., 2026](https://doi.org/10.1111/1752-1688.70089)). The formulation must be [BMI](https://doi.org/10.21105/joss.02317)-compliant and built into the NGIAB container ([Patel et al., 2025](https://doi.org/10.1016/j.envsoft.2025.106666)). [DataStreamCLI](https://github.com/CIROH-UA/datastreamcli) is the workflow tool for these. CFE-NOM and LSTM_0 are examples.

**General processing datastreams** run their own containerized processing on the NRDS schedule without touching NextGen. The deployed qkrig datastream interpolates streamflow observations spatially. Forcing preparation and the restart datastream are likewise non-simulating.

Each datastream type is explained below.

---

## NextGen Simulating Datastreams

A model formulation enters the NRDS by being expressed as a new execution specification pointing to a new realization file.

### 1. Get the model into the NGIAB container

NRDS simulations run in the maintained `awiciroh/ciroh-ngen-image` container, which we refer to as NGIAB. 

If your formulation is not already in a tagged image, open a [Model Integration Checklist](https://github.com/CIROH-UA/NGIAB-CloudInfra/issues/new?template=model_integration_request.yml) in NGIAB-CloudInfra. That template covers BMI implementation, dependencies, build instructions, and licensing. Once the model ships in a tagged release, you have the container version the datastream proposal asks for.

### 2. Exercise the configuration locally with DataStreamCLI

[DataStreamCLI](https://github.com/CIROH-UA/datastreamcli) runs the same workflow on your machine that the NRDS runs on schedule, in the same software environment. The distance between a working local DataStreamCLI run and a deployed datastream is short.

Save the commands you used. The proposal form (issue template) asks for them.

### 3. Open a proposal

Use the [Propose a New Datastream](https://github.com/CIROH-UA/ngen-datastream/issues/new?template=new_datastream.yml) template. The proposal asks for:

- The formulation: what it predicts, how it was developed or trained
- The NGIAB container semver tag it ships in, and every other container the processing needs
- What inputs it requires, and whether the NRDS already produces them
- Domain, cadence, and forecast configurations
- A walkthrough of a single processing run: input and output sizes, host resources used, duration
- A public, runnable example package and the DataStreamCLI commands that reproduce it
- How long the outputs should be retained
- The scientific rationale

The workflow walkthrough and example package matter most. They are what let us map your processing onto EC2 instance types and estimate what the datastream will cost to run.

---

## Non-NextGen Datastreams

Any scheduled, containerized processing workflow can become a datastream. Often these are connected to the NextGen simulating datastreams by creating their inputs (forcing) or post-processing outputs, or something else entirely like qkrig.

**Downstream applications.** Workflows that consume NRDS output: flood inundation mapping, water temperature, water quality, ground water contamination simulations, etc. These exercise the composability of the architecture directly.

**Alternative forcing preparation pipelines.** A new averaging or downscaling approach deployed as its own upstream datastream, rather than as a change to the shared Forcing Processor. 

**Hydrologic post-processing.** Bias correction or statistical post-processing applied to simulation output belongs here, as a downstream datastream consuming an upstream one.

**Observation processing.** qkrig is a deployed example: spatial interpolation of streamflow observations, running on the NRDS schedule, contributed by the community and deployed at continental scale about a month after its initial issue.

Use the same [Propose a New Datastream](https://github.com/CIROH-UA/ngen-datastream/issues/new?template=new_datastream.yml) template. Select the type that fits and leave the NGIAB container field blank.

---

## Ensembles and Probabilistic Configurations

The NRDS currently produces deterministic point forecasts (though the LSTM output is an ensemble average of sorts). Extending it to ensemble output would align it more closely with operational practice and support methods that produce distributions.

This spans ensemble realization files, forcing and initial-condition perturbation strategies, and the execution and output-organization patterns for managing members.

Cost is the central design constraint and belongs in the proposal directly. An N-member ensemble is roughly N times the compute and storage of its deterministic equivalent. State the member count, justify it, and identify what can be shared across members to reduce the multiple: shared forcings, shared warm states, reduced-domain configurations for development.

See this related [discussion](https://github.com/CIROH-UA/ngen-datastream/discussions/210).

---

## What Happens After You Open the Issue

The development team writes the pull request, working from your issue.

The datastream is expressed as a self-contained module holding its schedule definitions, forecast configuration, and execution template. See this [pull request](https://github.com/CIROH-UA/ngen-datastream/pull/330) if you're curious to investigate the exact mechanism of datastream deployment. Automated checks validate the configuration, preview the exact cloud resources the change creates, and run security and integration tests. 

Once a pull request is merged, the NRDS system will immediately scale up and begin orchestrating the new datastream. 
