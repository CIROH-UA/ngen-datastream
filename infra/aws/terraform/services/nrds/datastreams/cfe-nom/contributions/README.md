# Parameter contributions

Adding a YAML file deploys a parameter contribution. Present here on `main` means the
parameters were deployed at the time of the PR merge.

```yaml
issue:        400
url:          https://www.hydroshare.org/resource/9724840ce2f44072883a099371ca40af
last_updated: 2026-09-02T22:20:14.488159Z
type:         lumped            # or per_catchment
subdir:       gage-02369800     # the gage directory, when a package holds several
```

`last_updated` is the resource's `date_last_updated`, from
`https://www.hydroshare.org/hsapi/resource/<id>/sysmeta/`. It pins the version
that was reviewed. An unpublished hydroshare resource is mutable, so this time stamp is
used to ensure the contributed data file did not change since validation (PR creation). 

## How a contribution gets here

1. A contributor opens a [Contribute Calibrated Parameters](https://github.com/CIROH-UA/ngen-datastream/issues/new?template=parameter_contribution.yml)
   issue. A maintainer drafts the file above and runs **Parameter Contribution**
   from the Actions tab against it, relaying anything that needs fixing.
2. A maintainer opens a pull request adding the above yaml file corresponding to the contribution issue.
   That validates it, builds the merged realization, and runs it through a real short-range
   simulation of the VPU.
3. Merging to main archives the live realization and overwrites it.

The pull request is the staging step and the merge is the deployment. 
