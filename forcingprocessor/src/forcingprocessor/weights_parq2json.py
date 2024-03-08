import json, os
import concurrent.futures as cf
import numpy as np
import argparse, time
import geopandas as gpd
import pandas as pd
gpd.options.io_engine = "pyogrio"
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset

def get_catchment_idx(tbl,catchments):
    weight_data = {}
    ncatch_found = 0
    for _, jcatch in enumerate(catchments):         
        df_jcatch = tbl.loc[tbl['divide_id'] == jcatch]           
        ncatch_found+=1
        idx_list = [int(x) for x in list(df_jcatch['cell'])]
        df_catch = list(df_jcatch['coverage_fraction'])
        weight_data[jcatch] = [idx_list,df_catch]

    return weight_data

def get_weight_json(catchments,args):
    if args.version is None: 
        version = "v20.1"
    else:
        version = args.version
    print(f'Querying data from lynker-spatial')
    w = pa.dataset.dataset(
        f's3://lynker-spatial/{version}/forcing_weights.parquet', format='parquet'
    ).filter(
        pc.field('divide_id').isin(catchments)
    ).to_batches()
    batch: pa.RecordBatch
    ncatch_found = 0
    t_weights = time.perf_counter()    
    count = 0
    ncatchments = len(catchments)
    for batch in w:
        count += 1
        tbl = batch.to_pandas()
        if tbl.empty:
            continue    
        uni_cat = tbl.divide_id.unique()    
        located = [x for x in catchments if x in uni_cat]  
        [catchments.remove(x) for x in located]
        if len(located) > 0:
            nprocs = min(os.cpu_count(), args.nprocs_max,len(located))
            print(f'Calculating {len(located)} weights with {nprocs} processes')
            catchment_list = []  
            tbl_list = []    
            nper = ncatchments // nprocs
            nleft = ncatchments - (nper * nprocs)
            i = 0
            k = 0
            for _ in range(nprocs):
                k = nper + i + nleft      
                catchment_list.append(located[i:k])
                tbl_list.append(tbl)
                i = k

            with cf.ProcessPoolExecutor(max_workers=nprocs) as pool:
                results = pool.map(get_catchment_idx,tbl_list,catchment_list)

        weights = {}
        for jweights in results:
            weights = weights | jweights            

    print(f'Weights calculated for {len(weights)} catchments in {time.perf_counter() - t_weights:.1f} seconds')

    return weights

def get_catchments_from_gpkg(gpkg):
    catchments     = gpd.read_file(gpkg, layer='divides')
    catchment_list = sorted(list(catchments['divide_id']))  

    return catchment_list

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--gpkg', dest="geopackage", type=str, help="Path to geopackage file",default = None)
    parser.add_argument('--catchment_list', dest="catchment_list", type=str, help="list of catchments",default = None)
    parser.add_argument('--outname', dest="weights_filename", type=str, help="Filename for the weight file")
    parser.add_argument('--version', dest="version", type=str, help="Hydrofabric version e.g. \"v21\"",default = "v20.1")
    parser.add_argument('--nprocs', dest="nprocs_max", type=int, help="Maximum number of processes",default=os.cpu_count())
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
            print(f'Extracting conus weights')
            uri = f"s3://lynker-spatial/{version}/forcing_weights.parquet"
            weights_df = pd.read_parquet(uri) 
            catchment_list = list(weights_df.divide_id.unique())
            del weights_df
        else:
            if 's3://' in args.geopackage:
                weights_df = pd.read_parquet(args.geopackage) 
                catchment_list = list(weights_df.divide_id.unique())
                del weights_df
            else:
                print(f'Extracting weights from gpkg')
                catchment_list = get_catchments_from_gpkg(args.geopackage)

    weights = get_weight_json(catchment_list,args)

    data = json.dumps(weights)
    with open(args.weights_filename,'w') as fp:
        fp.write(data)
    