# Subset NGEN Hydrofabric
To subset a hydrofabric, run the script as follows

`python subset.py <path_to_hydrofabric> <catchment_id>`

where `path_to_hydrofabric` can be a local geopkg, or a remote resource (s3 or http URL),
and `catchment_id` is the catchment identifier of the downstream catchment you want included in the subset.

This will generate a new geopkg as well the ngen geojson files required to run ngen.

The subset algorithm will find all features upstream of the `catchment_id` and they will be included in the subset.

# Note
A current shortcut is being used to map `wb` and `cat` ids that isn't a valid assumption, and will be fixed in the future.
This means you might get a subset that isn't topologically consistent, so use at your own risk.

# ncatch_upstream
To get a list of how many catchments are upstream of each catchment, enter the following command
`python subset.py <path_to_hydrofabric> <path_to_output_text_file>`

where `path_to_hydrofabric` can be a local geopkg, or a remote resource (s3 or http URL),
and `path_to_output_text_file` is the full path to where you want the list output