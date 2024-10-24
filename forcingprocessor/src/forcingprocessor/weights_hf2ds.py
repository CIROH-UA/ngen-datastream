import json
import argparse, time
import geopandas as gpd
import re, os
import concurrent.futures as cf
import pandas as pd
gpd.options.io_engine = "pyogrio"   

def multiprocess_hf2ds(files : list):
    nprocs = min(len(files),os.cpu_count())
    i = 0
    k = 0
    nfiles = len(files)
    files_list = []
    nper = nfiles // nprocs
    nleft = nfiles - (nper * nprocs)    
    for i in range(nprocs):
        k = nper + i + nleft
        files_list.append(files[i:k])
        i=k

    weight_jsons = []
    jcatchment_dicts = []
    with cf.ProcessPoolExecutor(max_workers=nprocs) as pool:
        for results in pool.map(
        hf2ds,
        files_list,
        ):
            weight_jsons.append(results[0])
            jcatchment_dicts.append(results[1])    

    print(f'Processes have returned')
    weight_json = {}
    [weight_json.update(x) for x in weight_jsons]
    jcatchment_dict = {}
    [jcatchment_dict.update(x) for x in jcatchment_dicts]
  
    return weight_json, jcatchment_dict  


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
        pattern = r'vpuid%3D([^/]+)'
        match = re.search(pattern, jgpkg)
        if match: jname = "VPU_" + match.group(1)
        else:
            count +=1
            jname = str(count)    
        new_dict = hydrofabric2datastream_weights(jgpkg)
        weights_json = weights_json | new_dict
        jcatchment_dict[jname] = list(new_dict.keys())

    return weights_json, jcatchment_dict

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
            weights_json = json.load(fp)
        ncatchment = len(weights_json) 
    else:
        if weights_file.endswith('.gpkg'):
            catchments     = gpd.read_file(weights_file, layer='divides')
            weights_table  = gpd.read_file(weights_file, layer = 'forcing-weights')
        elif weights_file.endswith('parquet'):            
            weights_table     = pd.read_parquet(weights_file)
        else:
            raise Exception(f'Dont know how to deal with {weights_file}')
                    
        weights_table_unqiue_ids = weights_table.groupby('divide_id').agg(tuple).map(list).reset_index()
        catchments        = weights_table_unqiue_ids['divide_id']
        catchment_list    = sorted(set(list(catchments)))
        weights_table_unqiue_ids = weights_table_unqiue_ids.set_index('divide_id')
        weights_json = json.loads(weights_table_unqiue_ids.to_json(orient="index"))
        out_dict = {}
        for jcatch in weights_json:
            jlist = []
            jlist.append([int(x) for x in weights_json[jcatch]['cell']])
            jlist.append(weights_json[jcatch]['coverage_fraction'])
            out_dict[jcatch] = jlist
        tf = time.perf_counter()
        dt = tf - t0             
        ncatchment = len(catchment_list)   
        print(f'{ncatchment} catchment weights converted from tabular to json in {dt:.2f} seconds, {ncatchment/dt:.2f} catchments/second')
        return out_dict

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

    df = pd.DataFrame.from_dict(weights, orient='index',columns=['cell','coverage_fraction'])
    df = df.assign(divide_id=weights.keys()).set_index('divide_id')
    df.to_parquet(args.outname)
    
