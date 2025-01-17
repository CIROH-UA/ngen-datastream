# hfsubset - CLI-based Hydrofabric Subsetter

For those interested in using the NOAA NextGen fabric as is, we have
provided a Go-based CLI
[here](https://github.com/lynker-spatial/hfsubsetCLI/releases)

## Usage

This utility has the following syntax:

``` bash
hfsubset - Hydrofabric Subsetter

Usage:
  hfsubset [OPTIONS] identifiers...
  hfsubset (-h | --help)

Examples:
  hfsubset -o ./divides_nexus.gpkg \
           -r "2.2"                 \
           -t hl_uri                   \
           "Gages-06752260"

  hfsubset -o ./poudre.gpkg -t hl_uri "Gages-06752260"

  # Using network-linked data index identifiers
  hfsubset -o ./poudre.gpkg -t nldi "nwissite:USGS-08279500"
  
  # Specifying layers and hydrofabric version
  hfsubset -o ./divides_nexus.gpkg -r "2.2" -t hl_uri "Gages-06752260"
  
  # Finding data around a coordinate point
  hfsubset -o ./sacramento_flowpaths.gpkg -t xy -121.494400,38.581573

Environment Variables:
  ${HFSUBSET_ENDPOINT} - Endpoint to use for subsetting,
                         defaults to 'https://www.lynker-spatial.com/hydrofabric/hfsubset/'.
                         Note: the endpoint must end with a trailing slash.

Details:
  * Finding POI identifiers can be done visually
    through https://www.lynker-spatial.com/hydrolocations.html

  * When using identifier type 'xy', the coordinates are in OGC:CRS84 order,
    which is the same reference system as EPSG:4326 (WGS84), but uses
    longitude-latitude axis order rather than latitude-longitude.

  * When using identifier type 'nldi', the identifiers follow the syntax

      <featureSource>:<featureID>

    For example, USGS-08279500 is accessed with featureSource 'nwissite',
    so this gives the form 'nwissite:USGS-08279500'

Options:
  -debug
        Run in debug mode
  -dryrun
        Perform a dry run, only outputting the request that will be sent
  -l string
        Comma-delimited list of layers to subset. (default "divides,flowlines,network,nexus")
  -o string
        Output file name (default "hydrofabric.gpkg")
  -quiet
        Disable logging
  -s string
        Hydrofabric type, only "reference" is supported (default "reference")
  -t string
        One of: "hf", "comid", "hl", "poi", "nldi", or "xy" (default "hf")
  -v string
        Hydrofabric version (NOTE: omit the preceeding v) (default "2.2")
  -verify
        Verify that endpoint is available (default true)
  -w string
        Comma-delimited list of weights to generate over the subset.
```

### Generating Forcing Weights

The `-w` flag allows server-side generation of forcing weights on the requested subset,
as of v1.1.0, only `medium_range` is supported. Note that the `divides` layer must be
requested for this flag to be available.

```bash
hfsubset -w medium_range -t nldi "nwissite:USGS-08279500"
```

The above call will generate a subset `hydrofabric.gpkg` containing the
table `weight_grid_medium_range`.

## License

`hfsubset` is distributed under [GNU General Public License v3.0 or later](LICENSE.md)
