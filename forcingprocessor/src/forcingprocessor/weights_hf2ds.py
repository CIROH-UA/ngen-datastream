import json
import argparse, time
import geopandas as gpd
import boto3
import re
gpd.options.io_engine = "pyogrio"

def gpkgs2weightsjson(gpkg_files : list):
    """
    Extracts the weights from a list of geopackages

    input : gpkg_files
    gpkg_files : list of geooackage files

    returns : weights_json, jcatchment_dict
    weights_json : a dictionary where keys are catchment ids and the values are a list of weights
    jcatchment_dict : A dictionary where the keys are the geopackage name and the values are a list of catchment id's

    """
    weights_json = {}
    jcatchment_dict = {}
    count = 0
    for jgpkg in gpkg_files:
        ii_json = jgpkg.split('.')[-1] == "json"
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
            if ii_json: 
                new_dict = json.loads(jobj["Body"].read().decode())
            else:
                new_dict = hydrofabric2datastream_weights(jobj["Body"].read().decode())
        else:     
            if ii_json:
                with open(jgpkg, "r") as f:
                    new_dict = json.load(f)
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

def get_catchments_from_gpkg(gpkg):
    catchments     = gpd.read_file(gpkg, layer='divides')
    catchment_list = sorted(list(catchments['divide_id']))  
    return catchment_list

def hydrofabric2datastream_weights(gpkg : gpd.GeoDataFrame) -> dict:
    """
    Converts tabular weights to a dictionary where keys are catchment ids and the values are a list of weights
    
    input gpkg
    gpkg : gpd.Dataframe

    returns weights_json : a dictionary where keys are catchment ids and the values are a list of weights

    """
    t0 = time.perf_counter()
    catchments = get_catchments_from_gpkg(gpkg)
    ncatchment = len(catchments)
    weights_table    = gpd.read_file(gpkg, layer = 'forcing-weights')
    weights_json = get_catchment_idx(weights_table, catchments)
    tf = time.perf_counter()
    dt = tf - t0
    print(f'{ncatchment} catchment weights converted from tabular to json in {dt:.2f} seconds, {ncatchment/dt:.2f} catchments/second')
    return weights_json

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--gpkg', dest="gpkg", type=str, help="Path to geopackage file",default = None)
    parser.add_argument('--outname', dest="outname", type=str, help="Filename for the weight file")
    args = parser.parse_args()

    weights = hydrofabric2datastream_weights(args.gpkg)

    data = json.dumps(weights)
    with open(args.outname,'w') as fp:
        fp.write(data)
    
