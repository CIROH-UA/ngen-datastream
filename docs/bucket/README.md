# S3 Bucket: ciroh-community-ngen-datastream

This bucket contains outputs from the **NextGen Research DataStream (NRDS)**, an automated hydrologic simulation system that runs the NextGen Water Resources Modeling Framework operationally across CONUS. It provides daily forcing data, model simulation results, hydrofabric geopackages, and configuration files organized by 21 Vector Processing Units (VPUs). Data is updated continuously with short-range (18hr) and medium-range (10-day) forecasts.

## Root Folders

| Folder | Description | Usage |
|--------|-------------|-------|
| `outputs/` | NextGen model simulation results | Download ngen-run.tar.gz and troute NetCDF for streamflow data |
| `v2.2/` | Daily forcing files (current) | Download forcing NetCDF files as input for NextGen runs |
| `v2.1/` | Daily forcing files (legacy) | Legacy data from Oct 2024, use v2.2 for current runs |
| `v2.2_resources/` | Static resources per VPU | Download gpkg, BMI configs, and weights for simulation setup |
| `realizations/` | Model config JSONs | Use as templates for custom NextGen simulation configs |
| `parameters/` | Community parameters | Apply calibrated params to improve regional accuracy |
| `mappings/` | ID mapping files | Translate between NWM COMIDs and NextGen catchment IDs |
| `status/` | Dashboards | Check pipeline status and data availability |
| `submissions/` | Contributions | Reference example for submitting calibrated parameters |
| `forcingprocessor/` | FP test metadata | Internal testing for forcing processor validation |

---

## outputs/

Contains NextGen model simulation results from operational runs. Organized by model type (CFE, LSTM, or routing_only), date, forecast type (short_range, medium_range, or analysis_assim_extend), and VPU. Each run produces a complete ngen-run.tar.gz archive with catchment outputs and routed streamflow.

```
outputs/
+-- cfe_nom/v2.2_hydrofabric/ngen.{DATE}/
|   +-- short_range/{00-23}/VPU_{XX}/
|   +-- medium_range/{00,06,12,18}/1/VPU_{XX}/
|   +-- analysis_assim_extend/16/VPU_{XX}/
+-- lstm/v2.2_hydrofabric/ngen.{DATE}/
|   +-- short_range/{00-23}/VPU_{XX}/
|   +-- medium_range/{00,06,12,18}/1/VPU_{XX}/
|   +-- analysis_assim_extend/16/VPU_{XX}/
+-- routing_only/v2.2_hydrofabric/ngen.{DATE}/
```

**Each VPU folder contains:**

| File | Size | Description |
|------|------|-------------|
| `ngen-run.tar.gz` | 12-500MB | Complete simulation archive |
| `merkdir.file` | ~12MB | Integrity hash |
| `datastream-metadata/` | ~15KB | Execution configs and timing |
| `ngen-run/outputs/troute/*.nc` | ~4MB | Routed streamflow NetCDF |

**ngen-run.tar.gz contents:**

Complete NextGen simulation archive containing all inputs, configs, and outputs. Extract with `tar -xzf ngen-run.tar.gz`

```
ngen-run/
+-- config/
|   +-- nextgen_VPU_{XX}.gpkg           # 63MB hydrofabric geopackage
|   +-- realization.json                # 3.5KB NextGen realization config
|   +-- troute.yaml                     # 2KB T-Route routing config
|   +-- noah-owp-modular-init.*.pkl     # 4.4MB NOAH-OWP init pickle
|   +-- cat_config/                     # Per-catchment BMI configs
|       +-- CFE/                        # CFE config per catchment
|       +-- NOAH-OWP-M/                 # NOAH-OWP config per catchment
|       +-- PET/                        # PET config per catchment
+-- forcings/
|   +-- ngen.t{HH}z.*.forcing.*.nc      # 17-127MB forcing NetCDF
+-- outputs/
|   +-- ngen/
|   |   +-- cat-{ID}.csv                # ~17,600 per-catchment CSVs
|   +-- parquet/
|   |   +-- {YYYYMMDDHHMM}NEXOUT.parquet # 18 hourly nexus outputs (~85KB each)
|   +-- troute/                         # Empty in tar (see note below)
+-- lakeout/                            # Lake routing outputs (if applicable)
+-- restart/
|   +-- channel_restart_*               # ~314KB channel restart file
+-- partitions_3.json                   # 546KB MPI partition (3 proc)
+-- partitions_4.json                   # 274KB MPI partition (4 proc)
```

**Note:** The `troute_output_*.nc` file (~4MB routed streamflow) is stored separately in the VPU folder at `ngen-run/outputs/troute/`, not inside the tar.gz archive.

**datastream-metadata/ contents:**

- `execution.json` - Full run parameters
- `profile.txt` - Timing breakdown
- `docker_hashes.txt` - Image SHAs
- `conf_datastream.json` - Datastream config
- `conf_fp.json` - Forcing processor config
- `conf_nwmurl.json` - NWM URL config
- `datastream.env` - Environment variables
- `datastream_steps.txt` - Execution steps log
- `realization_user.json` - User realization
- `realization_datastream.json` - Final realization

---

## v2.2/

Daily pre-processed meteorological forcing files converted from NWM format to NextGen-compatible NetCDF. Updated every hour for short_range (18hr forecasts) and every 6 hours for medium_range (10-day forecasts). Files are partitioned by VPU for efficient regional access.

```
v2.2/ngen.{YYYYMMDD}/
+-- forcing_short_range/{00-23}/
|   +-- metadata/
|   |   +-- execution.json
|   |   +-- forcings_metadata/
|   |       +-- conf_fp.json, conf_nwmurl.json
|   |       +-- filenamelist.txt, profile_fp.txt
|   |       +-- weights.parquet (~149MB)
|   +-- ngen.t{HH}z.short_range.forcing.f001_f018.VPU_{XX}.nc
+-- forcing_medium_range/{00,06,12,18}/
|   +-- metadata/
|   +-- ngen.t{HH}z.medium_range.forcing.f001_f240.VPU_{XX}.nc
+-- forcing_analysis_assim_extend/16/
    +-- metadata/
    +-- ngen.t16z.analysis_assim_extend.forcing.tm27_tm00.VPU_{XX}.nc
```

**File sizes:**

| Type | Size per VPU | Forecast Hours |
|------|--------------|----------------|
| short_range | 17-127MB | f001-f018 (18hr) |
| medium_range | 216MB-1.6GB | f001-f240 (10 day) |
| analysis_assim_extend | 26-194MB | tm27-tm00 (28hr lookback) |

---

## v2.2_resources/

Static resources required for running NextGen simulations, including hydrofabric geopackages, BMI module configurations, and forcing weight files. These files are pre-computed per VPU and rarely change. Download once and reuse across multiple simulation runs.

```
v2.2_resources/
+-- VPU_{XX}/config/
|   +-- nextgen_VPU_{XX}.gpkg      # 63-490MB hydrofabric
|   +-- ngen-bmi-configs.tar.gz    # 2.5MB BMI configs
|   +-- partitions_4.json          # ~274KB MPI partition file
+-- weights/
|   +-- nextgen_VPU_{XX}_weights.json  # 9-47MB forcing weights
+-- conus_weights.parquet          # 154MB full CONUS weights
+-- lstm_conus_cat_config.tar.gz   # 78MB LSTM configs
+-- validator.tar.gz               # 32MB validation data
+-- datastream_ngen-run_pytest.tar.gz  # 172MB test data
+-- obj.json                       # 1.7KB object metadata
```

---

## realizations/

NextGen realization JSON files that define the model chain and parameters for each simulation. These configs specify which BMI modules to run (e.g., SLOTH, NOAH-OWP, CFE, LSTM) and how they connect. Use these as templates for custom runs.

| File | Size | Model Chain |
|------|------|-------------|
| `realization_VPU_{XX}.json` | 3.5KB | SLOTH > NOAH-OWP > PET > CFE > T-Route |
| `realization_VPU_16.json` | 390KB | Extended params for VPU 16 |
| `realization_rust_lstm_troute.json` | 1.7KB | LSTM > T-Route |
| `realization_lstm_python.json` | 1.7KB | Python LSTM |
| `realization_lstm_rust.json` | 1.7KB | Rust LSTM |
| `lumped_realization_example.json` | 6KB | Example lumped config |

---

## mappings/

Crosswalk files that map between National Water Model COMIDs and NextGen catchment/nexus IDs. Essential for translating NWM outputs to NextGen format or comparing results between the two modeling frameworks.

| File | Size | Description |
|------|------|-------------|
| `nwm_to_ngen_map.json` | 70MB | NWM COMID to NextGen catchment ID |
| `hf2.2_ref_hf_nexus_map.json` | 70MB | Hydrofabric nexus reference map |

---

## parameters/

Community-contributed calibrated model parameters that improve simulation accuracy for specific regions. These override default parameters and are submitted by researchers who have calibrated models against observed streamflow data.

| File | Size | Description |
|------|------|-------------|
| `parameters_16.parquet` | 4KB | Custom params for VPU 16 |

---

## status/

Operational monitoring dashboards showing the current state of the datastream pipeline. View run completion status, timing metrics, and AWS CloudWatch monitoring links. Check here first to verify if today's data is available.

| File | Size | Description |
|------|------|-------------|
| `dashboard.html` | 176KB | Main status dashboard |
| `cloudwatch_dashboard.html` | 646B | CloudWatch metrics link |

---

## submissions/

Community-contributed parameter files and model configurations. Researchers can submit calibrated parameters or custom configurations to be included in operational runs after review.

| File | Size | Description |
|------|------|-------------|
| `example_community_contribution.tar.gz` | 110KB | Example submission template |

---

## forcingprocessor/

Test metadata and outputs from the forcing processor component that converts NWM data to NextGen format. Used for validating forcing processor changes.

```
forcingprocessor/
+-- test/
    +-- metadata/
        +-- execution.json    # ~2.7KB test execution metadata
```

---

## Download Examples

```bash
# Output (model results)
aws s3 cp s3://ciroh-community-ngen-datastream/outputs/cfe_nom/v2.2_hydrofabric/ngen.20260116/short_range/12/VPU_09/ngen-run.tar.gz . --no-sign-request

# Forcing (input data)
aws s3 cp s3://ciroh-community-ngen-datastream/v2.2/ngen.20260116/forcing_short_range/12/ngen.t12z.short_range.forcing.f001_f018.VPU_09.nc . --no-sign-request

# Hydrofabric (geopackage)
aws s3 cp s3://ciroh-community-ngen-datastream/v2.2_resources/VPU_09/config/nextgen_VPU_09.gpkg . --no-sign-request

# Realization (model config)
curl -O https://ciroh-community-ngen-datastream.s3.amazonaws.com/realizations/realization_VPU_09.json

# Weights (forcing weights)
aws s3 cp s3://ciroh-community-ngen-datastream/v2.2_resources/weights/nextgen_VPU_09_weights.json . --no-sign-request
```

---

## VPUs

| VPU | Region | gpkg Size | Download |
|-----|--------|-----------|----------|
| 01 | New England | 102MB | [nextgen_VPU_01.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_01/config/nextgen_VPU_01.gpkg) |
| 02 | Mid-Atlantic | 168MB | [nextgen_VPU_02.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_02/config/nextgen_VPU_02.gpkg) |
| 03N | South Atlantic North | 157MB | [nextgen_VPU_03N.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_03N/config/nextgen_VPU_03N.gpkg) |
| 03S | South Atlantic South | 70MB | [nextgen_VPU_03S.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_03S/config/nextgen_VPU_03S.gpkg) |
| 03W | South Atlantic West | 162MB | [nextgen_VPU_03W.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_03W/config/nextgen_VPU_03W.gpkg) |
| 04 | Great Lakes | 185MB | [nextgen_VPU_04.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_04/config/nextgen_VPU_04.gpkg) |
| 05 | Ohio | 253MB | [nextgen_VPU_05.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_05/config/nextgen_VPU_05.gpkg) |
| 06 | Tennessee | 71MB | [nextgen_VPU_06.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_06/config/nextgen_VPU_06.gpkg) |
| 07 | Upper Mississippi | 307MB | [nextgen_VPU_07.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_07/config/nextgen_VPU_07.gpkg) |
| 08 | Lower Mississippi | 186MB | [nextgen_VPU_08.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_08/config/nextgen_VPU_08.gpkg) |
| 09 | Souris-Red-Rainy | 63MB | [nextgen_VPU_09.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_09/config/nextgen_VPU_09.gpkg) |
| 10L | Missouri Lower | 320MB | [nextgen_VPU_10L.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_10L/config/nextgen_VPU_10L.gpkg) |
| 10U | Missouri Upper | 490MB | [nextgen_VPU_10U.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_10U/config/nextgen_VPU_10U.gpkg) |
| 11 | Arkansas-Red-White | 355MB | [nextgen_VPU_11.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_11/config/nextgen_VPU_11.gpkg) |
| 12 | Texas-Gulf | 191MB | [nextgen_VPU_12.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_12/config/nextgen_VPU_12.gpkg) |
| 13 | Rio Grande | 134MB | [nextgen_VPU_13.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_13/config/nextgen_VPU_13.gpkg) |
| 14 | Colorado Upper | 172MB | [nextgen_VPU_14.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_14/config/nextgen_VPU_14.gpkg) |
| 15 | Colorado Lower | 212MB | [nextgen_VPU_15.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_15/config/nextgen_VPU_15.gpkg) |
| 16 | Great Basin | 179MB | [nextgen_VPU_16.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_16/config/nextgen_VPU_16.gpkg) |
| 17 | Pacific Northwest | 387MB | [nextgen_VPU_17.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_17/config/nextgen_VPU_17.gpkg) |
| 18 | California | 213MB | [nextgen_VPU_18.gpkg](https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/VPU_18/config/nextgen_VPU_18.gpkg) |
