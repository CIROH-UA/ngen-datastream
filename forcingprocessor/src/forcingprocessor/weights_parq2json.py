import concurrent.futures as cf
import json
import os, argparse, time
import geopandas as gpd
gpd.options.io_engine = "pyogrio"
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset

def get_weight_json(catchments,version=None):
    if version is None: version = "v20.1"
    
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
    for batch in w:
        tbl = batch.to_pandas()
        if tbl.empty:
            continue    
    
        for j, jcatch in enumerate(catchments):
            df_jcatch = tbl.loc[tbl['divide_id'] == jcatch]
            if df_jcatch.empty:
                continue  
            ncatch_found+=1
            weight_data[jcatch] = [[int(x) for x in list(df_jcatch['cell'])],list(df_jcatch['coverage_fraction'])]
    print(f'Weights calculated for {ncatch_found} catchments in {time.perf_counter() - t_weights:.1f} seconds')

    return (weight_data)

def get_catchments_from_gpkg(gpkg):
    catchments     = gpd.read_file(gpkg, layer='divides')
    catchment_list = sorted(list(catchments['divide_id']))  

    return catchment_list

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--gpkg', dest="geopackage", type=str, help="Path to geopackage file",default = None)
    parser.add_argument('--outname', dest="weights_filename", type=str, help="Filename for the weight file")
    parser.add_argument('--version', dest="version", type=str, help="Hydrofabric version e.g. \"v21\"",default = None)
    parser.add_argument('--nprocs', dest="nprocs_max", type=int, help="Maximum number of processes")
    args = parser.parse_args()

    version = args.version    
    weight_versions = ["v20.1",None]
    if version not in weight_versions: 
        raise Exception(f'version must one of: {weight_versions}')

    if args.geopackage is None:
        # go for conus
        import pandas as pd
        uri = f"s3://lynker-spatial/{version}/forcing_weights.parquet"
        weights_df = pd.read_parquet(uri)
        catchment_list = list(weights_df.divide_id.unique())
        del weights_df
    else:
        catchment_list = get_catchments_from_gpkg(args.geopackage)

    ncatchments = len(catchment_list)
    nprocs = min([os.cpu_count() // 5, args.nprocs_max,ncatchments])
    print(f'Querying weights with {nprocs} processes')
    catchment_list_list = []    
    nper = ncatchments // nprocs
    nleft = ncatchments - (nper * nprocs)
    i = 0
    k = 0
    for _ in range(nprocs):
        k = nper + i + nleft      
        catchment_list_list.append(catchment_list[i:k])
        i = k
    
    with cf.ProcessPoolExecutor(max_workers=nprocs) as pool:
        results = pool.map(get_weight_json,catchment_list_list)

    weights = {}
    for jweights in results:
        weights = weights | jweights

    data = json.dumps(weights)
    with open(args.weights_filename,'w') as fp:
        fp.write(data)
    