import geopandas as gpd
import numpy as np
import xarray as xr
from rasterio.features import rasterize, bounds
import json, argparse, os
from pathlib import Path
from math import floor, ceil
import datetime
import multiprocessing
from functools import partial

def process_row(row, grid):
    # Your existing row processing code here
    geom_rasterize = rasterize(
        [(row["geometry"], 1)],
        out_shape=grid.rio.shape,
        transform=grid.rio.transform(),
        all_touched=True,
        fill=0, 
        dtype="uint8",
    )
    # numpy.where runs slowly on large arrays
    # so we slice off the empty space
    y_min, x_max, y_max, x_min = bounds(row["geometry"], transform=~grid.rio.transform())
    x_min = floor(x_min)
    x_max = ceil(x_max)
    y_min = floor(y_min)
    y_max = ceil(y_max)
    geom_rasterize = geom_rasterize[x_min:x_max, y_min:y_max]
    localized_coords = np.where(geom_rasterize == 1)
    global_coords = (localized_coords[0] + x_min, localized_coords[1] + y_min)

    return (row["divide_id"], global_coords)

def generate_weights_file(geopackage,grid_file,weights_filepath):

    try:
        ds = xr.open_dataset(grid_file,engine='h5netcdf')
        grid = ds['RAINRATE']
        try:
            projection = ds.crs.esri_pe_string
        except:
            try:
                projection = ds.ProjectionCoordinateSystem.esri_pe_string
            except:
                raise Exception(f'\n\nCan\'t find projection!\n')
    except:
        raise Exception(f'\n\nThere\'s a problem with {example_grid_filepath}!\n')

    g_df = gpd.read_file(geopackage, layer='divides')
    gdf_proj = g_df.to_crs(projection)

    crosswalk_dict = {}
    start_time = datetime.datetime.now()
    print(f'Starting at {start_time}')
    rows = [row for _, row in gdf_proj.iterrows()]
    # Create a multiprocessing pool
    with multiprocessing.Pool() as pool:
        # Use a partial function to pass the constant 'grid' argument
        func = partial(process_row, grid=grid)
        # Map the function across all rows
        results = pool.map(func, rows)

    # Aggregate results
    for divide_id, global_coords in results:
        crosswalk_dict[divide_id] = global_coords


    weights_json = json.dumps(
        {k: [x.tolist() for x in v] for k, v in crosswalk_dict.items()}
    )
    print(f'Finished at {datetime.datetime.now()}')
    print(f'Total time: {datetime.datetime.now() - start_time}')
    with open(weights_filepath, "w") as f:
        f.write(weights_json)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(dest="geopackage", type=str, help="Path to geopackage file")
    parser.add_argument(dest="weights_filename", type=str, help="Filename for the weight file")
    example_grid_filepath = Path(Path(Path(os.path.dirname(__file__)).parent,'data/'),'nwm_example_grid_file.nc')
    if not example_grid_filepath.exists(): 
        print(f'{example_grid_filepath} doesn\'t exist, using user\'s input')
        parser.add_argument(dest="example_grid_filepath", type=str, help="Example NWM forcing file")        
    args = parser.parse_args()   
    if 'example_grid_filepath' in args: example_grid_filepath = args.example_grid_filepath 

    generate_weights_file(args.geopackage, example_grid_filepath, args.weights_filename)
