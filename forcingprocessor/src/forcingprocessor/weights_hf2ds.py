import json
import argparse, time
import geopandas as gpd
import boto3
import re, os
import concurrent.futures as cf
import pandas as pd
gpd.options.io_engine = "pyogrio"

def get_catchment_idx_mp(weights_table, catchment_list):
    ncatchments = len(catchment_list)
    nprocs = min(os.cpu_count()-2,ncatchments)
    catchments_list = []    
    weights_table_list = []
    nper = ncatchments // nprocs
    nleft = ncatchments - (nper * nprocs)
    i = 0
    k = 0
    for j in range(nprocs):
        k = nper + i
        if j == 0: k += nleft
        catchments_list.append(catchment_list[i:k])
        weights_table_list.append(weights_table)
        i = k

    weights_hf      = []
    with cf.ProcessPoolExecutor(max_workers=nprocs) as pool:
        for results in pool.map(
        get_catchment_idx,
        weights_table_list,
        catchments_list
        ):
            weights_hf.append(results)

    print(f'Processes have returned')
    weights_json = {}
    for j,jweight in enumerate(weights_hf):
        weights_json = weights_json | jweight

    return  weights_json   

def hf2ds(files : list):
    """
    Extracts the weights from a list of files

    input : files
    gpkg_files : list of geopackage or parquet files

    returns : weights_json, jcatchment_dict
    weights_json : a dictionary where keys are catchment ids and the values are a list of weights
    jcatchment_dict : A dictionary where the keys are the geopackage name and the values are a list of catchment id's

    """
    weights_json = {}
    jcatchment_dict = {}
    count = 0
    for jgpkg in files:
        ii_weights_in_bucket = jgpkg.find('//') >= 0
        pattern = r'VPU_([^/]+)'
        match = re.search(pattern, jgpkg)
        if match: jname = "VPU_" + match.group(1)
        else:
            count +=1
            jname = str(count)
        if ii_weights_in_bucket:
            s3 = boto3.client("s3")    
            jgpkg_bucket = jgpkg.split('/')[2]
            ii_uri = jgpkg.find('s3://') >= 0
            if ii_uri:
                jgpkg_key = jgpkg[jgpkg.find(jgpkg_bucket)+len(jgpkg_bucket)+1:]
            else:
                jgpkg_bucket = jgpkg_bucket.split('.')[0]
                jgpkg_key    = jgpkg.split('amazonaws.com/')[-1]
            jobj = s3.get_object(Bucket=jgpkg_bucket, Key=jgpkg_key)
            new_dict = hydrofabric2datastream_weights(jobj["Body"].read().decode())
        else:     
            new_dict = hydrofabric2datastream_weights(jgpkg)
        weights_json = weights_json | new_dict
        jcatchment_dict[jname] = list(weights_json.keys())

    return weights_json, jcatchment_dict

def get_catchment_idx(weights_table,catchments):
    weight_data = {}
    ncatch_found = 0
    for jcatch in catchments:         
        df_jcatch = weights_table.loc[weights_table['divide_id'] == jcatch]      
        ncatch_found+=1
        idx_list = [int(x) for x in list(df_jcatch['cell'])]
        df_catch = list(df_jcatch['coverage_fraction'])
        weight_data[jcatch] = [idx_list,df_catch]
    return (weight_data)

def hydrofabric2datastream_weights(weights_file : str) -> dict:
    """
    Converts tabular weights to a dictionary where keys are catchment ids and the values are a list of weights
    
    input gpkg or path to weights parquet
    gpkg : gpd.Dataframe

    returns weights_json : a dictionary where keys are catchment ids and the values are a list of weights

    """
    t0 = time.perf_counter()    

    if weights_file.endswith('.json'):
        with open(weights_file,'r') as fp:
            weights_file = json.load(fp)
    else:
        if weights_file.endswith('.gpkg'):
            catchments     = gpd.read_file(weights_file, layer='divides')
            weights_table  = gpd.read_file(weights_file, layer = 'forcing-weights')
            catchment_list = sorted(list(catchments['divide_id']))
        elif weights_file.endswith('parquet'):            
            weights_table     = pd.read_parquet(weights_file)
            catchments        = weights_table['divide_id']
            catchment_list    = sorted(set(list(catchments)))
            nunique = len(catchment_list)
            nrows   = len(list(catchments))
            if nrows == nunique:
                weights_table = weights_table.set_index('divide_id')
                weights_json = json.loads(weights_table.to_json(orient="index"))
                out_dict = {}
                for jcatch in weights_json:
                    jlist = []
                    jlist.append(weights_json[jcatch]['cell'])
                    jlist.append(weights_json[jcatch]['coverage_fraction'])
                    out_dict[jcatch] = jlist
                return out_dict
        else:
            raise Exception(f'Dont know how to deal with {weights_file}')
            
        ncatchment = len(catchment_list)
        if ncatchment > 5000:
            weights_json   = get_catchment_idx_mp(weights_table, catchment_list)
        else:
            weights_json   = get_catchment_idx(weights_table, catchment_list)

    tf = time.perf_counter()
    dt = tf - t0
    print(f'{ncatchment} catchment weights converted from tabular to json in {dt:.2f} seconds, {ncatchment/dt:.2f} catchments/second')
    return weights_json

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--input_file', dest="input_file", type=str, help="Path to geopackage or weights parquet file",default = None)
    parser.add_argument('--outname', dest="outname", type=str, help="Filename for the datastream weights file")
    args = parser.parse_args()

    weights, jcatchments = hf2ds(args.input_file.split(','))

    weights_prep = []
    for jweight in weights:
        cell = weights[jweight][0]
        cov  = weights[jweight][1]
        jdict = {}
        jdict['divide_id'] = jweight
        jdict['cell'] = cell
        jdict['coverage_fraction'] = cov
        weights_prep.append(jdict)

    df = pd.DataFrame.from_records(weights_prep)
    df.to_parquet(args.outname)
    
