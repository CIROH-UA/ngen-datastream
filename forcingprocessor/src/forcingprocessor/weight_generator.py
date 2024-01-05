import geopandas as gpd
import numpy as np
import xarray as xr
from rasterio.features import rasterize
import json, argparse, os
from pathlib import Path

def generate_weights_file(geopackage,grid_file,weights_filepath):

    try:
        ds = xr.open_dataset(grid_file,engine='h5netcdf')
        grid = ds['RAINRATE']
    except:
        raise Exception(f'\n\nThere\'s a problem with {example_grid_filepath}!\n')

    g_df = gpd.read_file(geopackage, layer='divides')
    gdf_proj = g_df.to_crs('PROJCS["Lambert_Conformal_Conic",GEOGCS["GCS_Sphere",DATUM["D_Sphere",SPHEROID["Sphere",6370000.0,0.0]], \
PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Lambert_Conformal_Conic_2SP"],PARAMETER["false_easting",0.0],\
PARAMETER["false_northing",0.0],PARAMETER["central_meridian",-97.0],PARAMETER["standard_parallel_1",30.0],\
PARAMETER["standard_parallel_2",60.0],PARAMETER["latitude_of_origin",40.0],UNIT["Meter",1.0]]')

    crosswalk_dict = {}
    i = 0
    for index, row in gdf_proj.iterrows():
        geom_rasterize = rasterize(
            [(row["geometry"], 1)],
            out_shape=grid.rio.shape,
            transform=grid.rio.transform(),
            all_touched=True,
            fill=0, 
            dtype="uint8",
        )
        crosswalk_dict[row["divide_id"]] = np.where(geom_rasterize == 1)


        if i % 100 == 0:
            perc = i / len(gdf_proj) * 100
            print(f"{i}, {perc:.2f}%".ljust(40), end="\r")
        i += 1

    weights_json = json.dumps(
        {k: [x.tolist() for x in v] for k, v in crosswalk_dict.items()}
    )
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
