# NRDS Datastream Catalog

Last Updated: July 2026

A static summary of every datastream the **NextGen Research Datastream (NRDS)** 
currently runs. Three tables are given that describe aspects of each datastream: the hydrology/modeling,
deployment configuration, and the characteristics of the technical backend driving the datastreams.
This document aims to answer the question *"what makes up the NRDS?"*
without having to read the bucket, code repositroy, or dashboard.

> **The NRDS is research-grade, not operational.** NRDS is an experimental testbed that runs the NextGen
> *prototype* on a forecast-like cadence to shrink research-to-operations (R2O) latency. It is
> **not** an operational forecasting system — the authoritative operational model is NOAA's
> National Water Model (NWM). Everything here is for research and evaluation, not
> decision-making. 

- **Deployment Snapshot:** For the running changelog and per-deployment history see
  [STATUS_AND_METADATA.md](./STATUS_AND_METADATA.md).
- **Live Status Page:** the [status dashboard](https://ciroh-community-ngen-datastream.s3.amazonaws.com/status/dashboard.html) reports daily simulation completion for every datastream. 
This page is a summary; the dashboard and the [public bucket](https://ciroh-community-ngen-datastream.s3.amazonaws.com/README.html) (`s3://ciroh-community-ngen-datastream`) 
holds the datastream outputs and related resources and metadata. All data used in the NRDS is public.
- **Definitions:** each datastream is defined by one technical execution specification under
  [`infra/aws/terraform/services/nrds/datastreams/`](../../infra/aws/terraform/services/nrds/datastreams).

All streams run on the **NextGen v2.2 hydrofabric** and split work **by VPU** (Vector
Processing Unit — a hydrologic sub-region). The `forcing`, `restart`, and `qkrig` streams
cover **full CONUS** (all 21 VPUs); the model streams `cfe-nom` and `lstm_0` run every VPU
**except 17** ([#199](https://github.com/CIROH-UA/ngen-datastream/issues/199)).

---

## Data locations

NRDS data is stored in the public bucket `s3://ciroh-community-ngen-datastream/` under the  `/forcings`, `/outputs`, and `/restart` prefixes (outputs are further keyed by `.../v2.2_hydrofabric/ngen.<date>/<run_type>/<init>/VPU_<id>/`).
**Dynamic inputs** are time-varying data fetched per run; **static inputs** are the fixed
hydrofabric/config resources shared across runs. Concrete examples (dated objects — swap the
date to browse current data): an example
forcing file - https://ciroh-community-ngen-datastream.s3.amazonaws.com/forcings/v2.2_hydrofabric/ngen.20260708/forcing_short_range/00/ngen.t00z.short_range.forcing.f001_f018.VPU_01.nc
and an example
cfe-nom streamflow file - https://ciroh-community-ngen-datastream.s3.amazonaws.com/outputs/cfe_nom/v2.2_hydrofabric/ngen.20260708/short_range/00/VPU_09/ngen-run/outputs/troute/troute_output_202607080100.parquet

---

## Table 1 — Methods, Inputs & Outputs

*Method, purpose, the dynamic and static inputs each stream consumes, what it produces, and who
maintains it.*

| Datastream | Model / method | Purpose | Dynamic inputs | Static inputs | Outputs | Status |
|---|---|---|---|---|---|---|
| `forcing` | [forcingprocessor](https://github.com/CIROH-UA/forcingprocessor) grid→catchment remap | Convert gridded NWM meteorologic forcings into NextGen-compatible catchment-averaged forcings; shared input for all model NextGen datastreams | NWM v3 forcings | `resources/v2.2_hydrofabric` | Catchment-averaged forcings · NetCDF/VPU · `forcings/` | Running |
| `cfe-nom` | [NOAH-OWP-Modular](https://github.com/NOAA-OWP/noah-owp-modular) (NOM) + [CFE](https://github.com/NOAA-OWP/cfe) + [PET](https://github.com/NOAA-OWP/evapotranspiration) + [t-route](https://github.com/NOAA-OWP/t-route) | Continental process-based hydrologic simulation with community-tuned parameters | `forcing` outputs | `resources/v2.2_hydrofabric` (per-VPU realizations, BMI configs, geopackage) | Streamflow · Parquet · `outputs/cfe_nom/` | Running |
| `lstm_0` | Rust LSTM ([NeuralHydrology](https://github.com/neuralhydrology/neuralhydrology)-trained) + [t-route](https://github.com/NOAA-OWP/t-route) | ML streamflow benchmark running the **first two** LSTM ensembles (weights 0-1) | `forcing` outputs | `resources/v2.2_hydrofabric`; 2 LSTM weight sets | Streamflow · Parquet · `outputs/lstm_0/` | Running |
| `lstm` | Rust LSTM ([NeuralHydrology](https://github.com/neuralhydrology/neuralhydrology)-trained) + [t-route](https://github.com/NOAA-OWP/t-route) | ML streamflow benchmark running the **full six** LSTM ensembles (weights 0–5) | `forcing` outputs | `resources/v2.2_hydrofabric`; 6 LSTM weight sets | Streamflow · Parquet · `outputs/lstm/` | Stopped |
| `routing-only` | [SLoTH](https://github.com/NOAA-OWP/SLoTH) + [t-route](https://github.com/NOAA-OWP/t-route) (no land-surface model) | Isolate/benchmark channel routing from NWM lateral inflows | NWM `CHRTOUT` q_lateral; `restart` files | `resources/v2.2_hydrofabric` (geopackage, crosswalk) | Streamflow · Parquet · `outputs/routing_only/` | Running |
| `restart` | [forcingprocessor](https://github.com/CIROH-UA/forcingprocessor) remap of NWM channel state | Generate t-route initial-condition files consumed by `routing-only` | NWM channel routing | `resources/v2.2_hydrofabric` | Channel restart states · NetCDF · `restarts/` | Running |
| `qkrig` | Ordinary kriging of gauge discharge over CONUS, sampled at catchment centroids | Provide a gridded streamflow "observation" field for calibration, evaluation, and data assimilation | USGS IV discharge | `resources/v2.2_hydrofabric/conus_nextgen.gpkg` | Kriged discharge field · NetCDF + Parquet + PNG/GIF · `outputs/qkrig/` | Running |

> `lstm` is currently **stopped** (no longer scheduled) and is omitted from Tables 2 and 3; all
> other streams are running.

**Realizations** (the NextGen configuration each stream runs) are public and versioned:

- cfe-nom — `realizations/cfe_nom/realization_VPU_<VPU>.json` (per-VPU, holds mutable
  [community parameters](https://datastream.ciroh.org/index.html#parameters/))
- lstm_0 — `realizations/lstm/realization_rust_lstm_troute.json`
- routing-only — `realizations/routing_only/realization_sloth_troute.json`

To propose parameter changes, see [CONTRIBUTE.md](./CONTRIBUTE.md).

---

## Table 2 — Deployment (cadence, domain, lead time)

*Forecast configurations, spatial coverage, and forecast horizon / latency.*

| Datastream | Forecast configs | Init cadence | Spatial domain | Forecast horizon | Latency (data → bucket)¹ |
|---|---|---|---|---|---|
| `forcing` | short_range, medium_range, analysis_assim_extend | SR 24×/day (hourly); MR 4×/day (00/06/12/18); AnA 1×/day (16z) | Full CONUS | SR 18 h; MR 240 h (10 d); AnA 28 h retrospective | minutes |
| `cfe-nom` | short_range, medium_range, analysis_assim_extend | SR hourly; MR 4×/day (member 1); AnA 16z | CONUS, all VPUs but 17 | SR 18 h; MR 240 h; AnA 28 h | ~minutes/VPU |
| `lstm_0` | short_range, medium_range, analysis_assim_extend | SR hourly; MR 4×/day (member 1); AnA 16z | CONUS, all VPUs but 17 | SR 18 h; MR 240 h; AnA 28 h | ~minutes/VPU |
| `routing-only` | short_range | Hourly | VPU 03W only | SR 18 h | ~minutes |
| `restart` | analysis_assim (channel restart) | Hourly (24 init cycles) | Full CONUS | n/a (analysis state) | ~minutes |
| `qkrig` | daily | 1×/day, 00:30 ET (prior UTC day) | Full CONUS | n/a (24 h analysis) | hours |

¹ Latency is the wall-clock from fetching source data to writing outputs to S3 for a single
unit of work. A representative process-based VPU run (e.g. VPU 13) completes in ~100 s;
`qkrig` is a single continental job. These are typical
figures, not SLAs — check the dashboard for current completion times.

**Forecast run types** (NWM conventions, reused by NRDS):

- **short_range (SR)** — hourly-initialized 18-hour forecast (`f001`–`f018`).
- **medium_range (MR)** — 6-hourly-initialized 10-day (240 h) forecast (`f001`–`f240`).
  NRDS currently runs the **first ensemble member only** (scaled back 10/2025).
- **analysis_assim_extend (AnA)** — once-daily 28-hour retrospective analysis
  (`tm27`–`tm00`), used to establish current conditions.

---

## Table 3 — Technical / backend

*Compute platform, instance sizing, and container versions. The current deployment runs on
**AWS**; an **LXD/HPC** port (University of Arizona "Nextstream") is in development (see FAQ).*

| Datastream | Platform | Instance type(s)² | Disk (GB gp3) | Container images (current)³ |
|---|---|---|---|---|
| `forcing` | AWS EC2 (Graviton) | SR/AnA `m8g.2xlarge`; MR `m8g.4xlarge` | 64 | `awiciroh/datastream:1.0.2`, `awiciroh/forcingprocessor:1.0.3` |
| `cfe-nom` | AWS EC2 (Graviton) | `m8g.xlarge` → `m8g.4xlarge` (scales with VPU and MR) | 64 | `awiciroh/datastream:1.7.1` + `awiciroh/ciroh-ngen-image:v1.8.0` |
| `lstm_0` | AWS EC2 (Graviton) | `m8g.2xlarge` → `m8g.4xlarge` (scales with VPU and MR) | 64 | `awiciroh/datastream:1.7.1` + `awiciroh/ciroh-ngen-image:v1.8.0` |
| `routing-only` | AWS EC2 (Graviton) | `m8g.large` | 64| `awiciroh/datastream:1.7.0` + `awiciroh/ciroh-ngen-image:v1.7.0` |
| `restart` | AWS EC2 (Graviton) | `m8g.2xlarge` | 64 | `awiciroh/datastream:1.7.0`, `awiciroh/forcingprocessor:2.2.1` |
| `qkrig` | AWS EC2 (Graviton) | `m8g.4xlarge` | 100 | `awiciroh/qkrig:2.2.0` |

² **AWS Graviton (`m8g`, ARM64)** sizing:

| Instance | vCPU | RAM |
|---|---|---|
| `m8g.large` | 2 | 8 GB |
| `m8g.xlarge` | 4 | 16 GB |
| `m8g.2xlarge` | 8 | 32 GB |
| `m8g.4xlarge` | 16 | 64 GB |

Per-VPU sizing is set in each stream's `config/execution_forecast_inputs*.json`; larger VPUs
(e.g. 05, 07, 10L, 10U) get the bigger instance.

### Containers

Each image is built from a source project on GitHub and pulled from Docker Hub (no Dockerfiles
live in this repo):

| Docker image | Source project | Selected by | Role |
|---|---|---|---|
| `awiciroh/datastream` | [datastreamcli](https://github.com/CIROH-UA/datastreamcli) | `DS_TAG` | DataStreamCLI tooling / workflow |
| `awiciroh/forcingprocessor` | [forcingprocessor](https://github.com/CIROH-UA/forcingprocessor) | `FP_TAG` | grid→catchment forcing remap |
| `awiciroh/ciroh-ngen-image` | [NGIAB-CloudInfra](https://github.com/CIROH-UA/NGIAB-CloudInfra) | `NGIAB_TAG` | NextGen/NGIAB runtime |
| `awiciroh/qkrig` | [DualEarth/qkrig](https://github.com/DualEarth/qkrig) | pinned `2.2.0` | ordinary-kriging observation field |
| `zwills/merkdir` | [makew0rld/merkdir](https://github.com/makew0rld/merkdir) | (untagged) | output-tree checksum utility |

³ Image tags are **pinned per datastream** in the execution template
(`templates/*.tpl`), not globally — this is why streams can run different versions. The
repository default is in [`ami_version.yml`](../../ami_version.yml): `DS_TAG 1.7.1`,
`FP_TAG 2.2.1`, `NGIAB_TAG v1.8.0`, AMI `1.7.1`. Docker tags follow `MAJOR.MINOR.PATCH` and
are traceable to GitHub commits, so any run is reconstructable from its metadata. **Note:**
`cfe-nom` and `forcing` currently pin older tags than the repo default — worth reconciling.

---

## FAQ / Appendix

### What is a "datastream"?
A datastream is a versioned, scheduled processing pipeline defined by five things: its
**inputs, processing, outputs, cadence, and execution environment**. Adding one is an
*additive* change — a new execution specification, no infrastructure changes. See
[datastreamcli options](https://github.com/CIROH-UA/datastreamcli/blob/main/docs/DATASTREAM_OPTIONS.md) and [standard output directories](https://github.com/CIROH-UA/datastreamcli/blob/main/docs/STANDARD_DIRECTORIES.md).

### How is the time axis constructed?
Times follow NWM conventions: `t{HH}z` is the initialization/reference hour (e.g.
`NWM_V3_SHORT_RANGE_00` → 00Z), `f{NNN}` a forward step, `tm{NNN}` a retrospective step; data
is hourly. Runs are **cold-start** (no warm state), so the forcing and NGEN time axes begin at
**init + 1 h** (e.g. 01:00Z) and run to init + horizon. t-route output is offset a further
**+1 h** from NGEN — each t-route stamp is the mean flow over the *preceding* hour — so its
first stamp is init + 2 h. The flow values are correct; the subtlety is labeling: the path's
init hour, the filename / `file_reference_time` (= first value), and the `time` coordinate do
not coincide. Full step-by-step trace and status:
[datastreamcli#32](https://github.com/CIROH-UA/datastreamcli/issues/32).

### What meteorological variables are in the forcings?
Remapped from NWM v3 gridded (~1 km) data to catchment-averaged values, hourly. Variables in a
forcing NetCDF (per-VPU file, dimensions `catchment-id` × `time`):

| Variable | Description | Units¹ |
|---|---|---|
| `APCP_surface` | Total precipitation (hourly accumulation) | kg m⁻² (≈ mm) |
| `precip_rate` | Precipitation rate | kg m⁻² s⁻¹ |
| `TMP_2maboveground` | Air temperature at 2 m | K |
| `SPFH_2maboveground` | Specific humidity at 2 m | kg kg⁻¹ |
| `UGRD_10maboveground` | Eastward (U) wind at 10 m | m s⁻¹ |
| `VGRD_10maboveground` | Northward (V) wind at 10 m | m s⁻¹ |
| `PRES_surface` | Surface pressure | Pa |
| `DSWRF_surface` | Downward shortwave radiation at surface | W m⁻² |
| `DLWRF_surface` | Downward longwave radiation at surface | W m⁻² |
| `Time` | Valid time, seconds since 1970-01-01 (hourly) | s |
| `ids` | NextGen catchment id | — |

¹ The files carry no unit attributes; units follow NWM/AORC conventions and are consistent
with observed magnitudes (e.g. `TMP` ≈ 287 K, `PRES` ≈ 101,900 Pa, `DLWRF` ≈ 373 W m⁻²).

### What outputs does a model run produce?
Per VPU per run, the primary output is the **t-route streamflow Parquet** (channel discharge by
feature and time), plus a `datastream-metadata/` directory binding code + data + environment
(image hashes, `execution.json`, input inventory, command history) for reproducibility. The
older `ngen-run.tar.gz` bundle (realization, BMI configs, hydrofabric subset, raw ngen and
t-route NetCDF) was **deprecated in July 2026**. See
[STANDARD_DIRECTORIES.md](https://github.com/CIROH-UA/datastreamcli/blob/main/docs/STANDARD_DIRECTORIES.md).

### What is *not* currently ingested?
NRDS currently ingests **NWM v3 meteorological forcings**, **NWM channel routing state**
(restart), and **USGS gauge discharge** (qkrig). It does **not** yet ingest, for example:
independent meteorological/climate forecast ensembles, or satellite datasets (SWE, soil
moisture, ET). Gauge discharge enters only as the kriged `qkrig` field, not yet as direct
model data assimilation. These are candidate additions — each would be a new datastream.

### How does it run — is there a scheduler / HPC cluster?
On AWS, an **EventBridge Scheduler** cron triggers a **Step
Functions state machine** per VPU per cycle; five Lambdas
(`EC2StarterFromAMI → Commander → EC2Poller → RunChecker → EC2Stopper`) launch an EC2
instance from an AMI, run the datastreamcli command, verify the S3 output exists, then
terminate the instance and detach the volume. See
[ARCHITECTURE.md](../../infra/aws/terraform/docs/ARCHITECTURE.md). An **LXD-based HPC** port
(UA "Nextstream") replaces the scheduler + state machine with an always-on controller
(APScheduler + Python orchestrator, 2 vCPU / 4 GiB) launching ephemeral LXD workers sized
like the `m8g` instances; it currently mirrors the `forcing` and `cfe-nom` streams and is in
development.

### Where do I find the data, status, and viewers?
| | |
|---|---|
| Public data bucket | https://ciroh-community-ngen-datastream.s3.amazonaws.com/README.html |
| Status dashboard | https://ciroh-community-ngen-datastream.s3.amazonaws.com/status/dashboard.html |
| Data product browser | https://communityhydrofabric.s3.us-east-1.amazonaws.com/datastream_viewer.html |
| Tethys NRDS visualizer | https://nrds.ciroh.org/ |
| TEEHR evaluation dashboards | https://dashboards.teehr.rtiamanzi.org/forecast |

### How do I add or change a datastream?
It's a PR review cycle, not infrastructure work: develop/test locally with
DataStreamCLI/NGIAB → open a PR adding an execution spec → automated config check, resource
plan preview, and integration tests post on the PR → gated merge → a daily drift check keeps
the deployment honest. See [CONTRIBUTE.md](./CONTRIBUTE.md).
