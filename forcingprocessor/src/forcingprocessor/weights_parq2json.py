import concurrent.futures as cf
import json
import numpy as np
import os, argparse, time
import geopandas as gpd
gpd.options.io_engine = "pyogrio"
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset

def get_weight_json(catchments,version=None):
    if version is None: version = "v20.1"

    data_shp = (3840,4608)
    
    weight_data = {}
    print(f'Beginning weights query')
    w = pa.dataset.dataset(
        f's3://lynker-spatial/{version}/forcing_weights.parquet', format='parquet'
    ).filter(
        pc.field('divide_id').isin(catchments)
    ).to_batches()
    batch: pa.RecordBatch
    ncatch_found = 0
    t_weights = time.perf_counter()    
    [x_min, x_max] = [10000,0]
    [y_min, y_max] = [10000,0]
    for batch in w:
        tbl = batch.to_pandas()
        if tbl.empty:
            continue    
    
        for j, jcatch in enumerate(catchments):
            df_jcatch = tbl.loc[tbl['divide_id'] == jcatch]
            if df_jcatch.empty:
                continue  
            ncatch_found+=1
            idx_list = [int(x) for x in list(df_jcatch['cell'])]
            df_catch = list(df_jcatch['coverage_fraction'])
            weight_data[jcatch] = [idx_list,df_catch]
            [x,y] = np.unravel_index(idx_list,(data_shp[0], data_shp[1]))
            jxmin = min(x)
            jxmax = max(x)
            jymin = min(y)
            jymax = max(y)
            if jxmin < x_min: x_min = jxmin
            if jxmax > x_max: x_max = jxmax
            if jymin < y_min: y_min = jymin
            if jymax > y_max: y_max = jymax
    
    print(f'Weights calculated for {ncatch_found} catchments in {time.perf_counter() - t_weights:.1f} seconds')

    return (weight_data, int(x_min), int(x_max), int(y_min), int(y_max))

def get_catchments_from_gpkg(gpkg):
    catchments     = gpd.read_file(gpkg, layer='divides')
    catchment_list = sorted(list(catchments['divide_id']))  

    return catchment_list

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--gpkg', dest="geopackage", type=str, help="Path to geopackage file",default = None)
    parser.add_argument('--catchment_list', dest="catchment_list", type=str, help="list of catchments",default = None)
    parser.add_argument('--outname', dest="weights_filename", type=str, help="Filename for the weight file")
    parser.add_argument('--version', dest="version", type=str, help="Hydrofabric version e.g. \"v21\"",default = None)
    parser.add_argument('--nprocs', dest="nprocs_max", type=int, help="Maximum number of processes",default=1)
    args = parser.parse_args()

    version = args.version    
    weight_versions = ["v20.1",None]
    if version not in weight_versions: 
        raise Exception(f'version must one of: {weight_versions}')

    if args.catchment_list is not None:
        catchment_list = args.catchment_list.split(',')
    else:
        if args.geopackage is None:
            # go for conus
            import pandas as pd
            uri = f"s3://lynker-spatial/{version}/forcing_weights.parquet"
            weights_df = pd.read_parquet(uri) 
            catchment_list = list(weights_df.divide_id.unique())
            del weights_df
        else:
            catchment_list = get_catchments_from_gpkg(args.geopackage)

    (weights, x_min, x_max, y_min, y_max) = get_weight_json(catchment_list)

    weights['window'] = [x_min,x_max,y_min,y_max]

    data = json.dumps(weights)
    with open(args.weights_filename,'w') as fp:
        fp.write(data)
    