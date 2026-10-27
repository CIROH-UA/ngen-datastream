# Hydrofabric contributions

Adding a YAML file deploys a hydrofabric contribution: one or more whole-VPU
geopackages. Present here on `main` means the geopackages and the BMI configurations built
from them were uploaded at the time of the PR merge. A VPU runs them once its
`vpu_resource_overrides` entries point at them.

```yaml
issue:        423
url:          https://www.hydroshare.org/resource/c128e9bf32df4de587b86d698e1b6831
last_updated: 2026-10-20T20:41:46.431375Z
vpus:         ["17"]            # every VPU in the package, quoted, as named in the NRDS
```

The file describes only the contribution. `last_updated` is the resource's
`date_last_updated`, from `https://www.hydroshare.org/hsapi/resource/<id>/sysmeta/`. It
pins the version that was reviewed, as for
[parameter contributions](../../datastreams/cfe-nom/contributions/README.md). The resource
must be public for the workflow to read it.

## What is accepted

A package holding one geopackage per VPU, as bare `.gpkg` files or tarred together, on
hydrofabric v2.2. Each geopackage covers one whole VPU; subsets are not accepted. It must
carry every layer and column of the geopackage it replaces. `vpus` must list exactly the
VPUs the package holds, which is read from each geopackage's `divides.vpuid`, not from
its file name.

## How a contribution gets here

1. A contributor opens a [Contribute a Hydrofabric Update](https://github.com/CIROH-UA/ngen-datastream/issues/new?template=hydrofabric_contribution.yml)
   issue. A maintainer drafts the file above and runs **Hydrofabric Contribution**
   from the Actions tab against it, relaying anything that needs fixing.
2. A maintainer opens a pull request adding the file. For every VPU the workflow
   - checks the candidate against the geopackage production runs, as the datastreams'
     `main.tf` name it: integrity, layers and columns, identifier format, and dangling
     references,
   - reports what differs, and which derived resources that leaves stale,
   - builds the cfe-nom and lstm_0 BMI configurations from the candidate with the
     [BMI Configurations](../../../../../../../.github/workflows/bmi_configs.yml) workflow,
     using the datastreamcli version each datastream runs,
   - runs the [Datastream VPU Test](../../../../../../../.github/workflows/datastream-vpu-test.yml)
     with the candidate and its new configurations swapped in: a short-range execution
     of the VPU in each of cfe-nom, lstm_0 and routing-only that schedules it, through
     the production state machine on the production instance.

   The workflow comments the checks and builds, and the VPU test comments each
   execution. A VPU no datastream schedules yet is checked and built but not run.
3. Merging uploads: the checks run again on what was merged, then every geopackage and
   its BMI tarballs are uploaded under the issue number. The run's summary lists the
   `vpu_resource_overrides` entries that put them to use, also printed by
   `python -m research_datastream.contribution_hydrofabric overrides <file>`.
4. A maintainer opens a pull request adding those entries to `datastreams/cfe-nom/main.tf`,
   `datastreams/lstm_0/main.tf` and `datastreams/routing-only/main.tf`. Its Datastream VPU
   Test runs the deployed files, and merging it applies Terraform.

The test answers whether a geopackage breaks a production datastream. It does not
judge whether outputs improve. The pull requests, linked to the issue and to the workflow
runs, are the record of the contribution.

## Deployment

Nothing is overwritten. A contribution's files are written under its issue number:

```
resources/v2.2_hydrofabric/
├── geopackages/
│   ├── VPU_17/nextgen_VPU_17.gpkg                                   original
│   └── contributions/423/nextgen_VPU_17.gpkg                        deployed by #423
└── bmi_configs/
    ├── cfe_nom_fixed/VPU_17/ngen-bmi-configs.tar.gz                 original
    ├── cfe_nom/contributions/423/VPU_17/ngen-bmi-configs.tar.gz     built from #423
    └── lstm_0/
        ├── VPU_17/ngen-bmi-configs.tar.gz                           original
        └── contributions/423/VPU_17/ngen-bmi-configs.tar.gz         built from #423
```

The BMI tarballs keep a `VPU_XX` directory because datastreamcli requires the file name
`ngen-bmi-configs.tar.gz`.

Which files a VPU's executions use is set by hand in each datastream's `main.tf`, where
`vpu_resource_overrides` replaces the default `geopackage` and `bmi_configs` keys of the
VPUs it lists. A later contribution for the same VPU gets its own issue directory, so every
geopackage that has ever run stays where it was, and going back is an edit to those
entries.

BMI configurations can also be rebuilt without a new geopackage, for example after a
datastreamcli update, by running **BMI Configurations** from the Actions tab with the
datastreamcli version and an S3 prefix, then pointing `bmi_configs` at the result.

## What deployment does not update

The geopackage is the source of several other NRDS inputs besides the BMI
configurations. The workflow's report lists the ones a contribution leaves stale; these
are updated by hand.

| If the candidate changes | Also update | Read by |
|---|---|---|
| anything, if qkrig should see it | `conus_nextgen.gpkg` | qkrig |
| divides added, removed or reshaped | forcing weights: `weights/nextgen_VPU_XX_weights.json` and the copy baked into the AMI | forcing |
| divide identifiers | `troute_restart/hf2.2_ref_hf_catchment_map.json` | restart, and so cfe-nom and lstm_0 |
| nexus identifiers | `mappings/nwm_to_ngen_map.json` | routing-only |
| flowpath identifiers or connectivity | `troute_restart/crosswalk.nc` (verify) | restart |
| a VPU not yet scheduled | the VPU lists in `forcing/schedules.tf`, `cfe-nom/main.tf`, `lstm_0/main.tf` and each `execution_forecast_inputs_*.json` | all |

All paths are under `s3://ciroh-community-ngen-datastream/resources/v2.2_hydrofabric/`
except `mappings/`, which is at the bucket root.
