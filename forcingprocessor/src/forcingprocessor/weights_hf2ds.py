import json, os
import concurrent.futures as cf
import argparse, time
import geopandas as gpd
import pandas as pd
gpd.options.io_engine = "pyogrio"
import fiona

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

def get_catchments_from_gpkg(gpkg):
    catchments     = gpd.read_file(gpkg, layer='divides')
    catchment_list = sorted(list(catchments['divide_id']))  
    return catchment_list

def hydrofabric2datastream_weights(gpkg):
    t0 = time.perf_counter()
    layers = fiona.listlayers(gpkg)
    catchments = get_catchments_from_gpkg(gpkg)
    ncatchment = len(catchments)
    weights_layer = [x for x in layers if "weights" in x]
    if len(weights_layer) == 0:
        raise Exception('forcing weights not found in geopackage! Use hfsubset with appropriate options.')
    else:
        weights_layer = weights_layer[0]
    weights_table    = gpd.read_file(gpkg, layer = weights_layer)
    weights_datastream = get_catchment_idx(weights_table, catchments)
    tf = time.perf_counter()
    dt = tf - t0
    print(f'{ncatchment} datastream weights calculated in {dt:.2f} seconds, {dt/ncatchment:.2f} seconds/catchment ')

    return weights_datastream

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--gpkg', dest="gpkg", type=str, help="Path to geopackage file",default = None)
    parser.add_argument('--outname', dest="outname", type=str, help="Filename for the weight file")
    args = parser.parse_args()

    weights = hydrofabric2datastream_weights(args.gpkg)

    data = json.dumps(weights)
    with open(args.outname,'w') as fp:
        fp.write(data)
    
