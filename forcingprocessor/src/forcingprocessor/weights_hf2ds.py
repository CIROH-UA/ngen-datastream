import json, re, argparse, time, requests, os
from io import BytesIO
import geopandas as gpd
import concurrent.futures as cf
import pandas as pd
import xarray as xr
import numpy as np
gpd.options.io_engine = "pyogrio" 

def rastersourceNexactextract(raster_data,geo_data):
    from exactextract import exact_extract
    from exactextract.raster import NumPyRasterSource
    ncatch_proc = len(geo_data)

    print(f'Finding weights for geodataframe of size {ncatch_proc}',flush=True)
    xmin = raster_data.x[0]
    xmax = raster_data.x[-1]
    ymin = raster_data.y[0]
    ymax = raster_data.y[-1]
    # print(f"window {xmin.value} {xmax.value} {ymin.value} {ymax.value}")
    t0 = time.perf_counter()
    rastersource = NumPyRasterSource(
            np.squeeze(raster_data["T2D"]), 
            srs_wkt=geo_data.crs.to_wkt(), 
            xmin=xmin, 
            xmax=xmax, 
            ymin=ymin, 
            ymax=ymax  
        ) 
    print(f'raster calculated, executing exactextract',flush=True)
    output = exact_extract(
        rastersource,
        geo_data,
        ["cell_id", "coverage"],
        include_cols=["divide_id"],
        output="pandas",
    )
    tf = time.perf_counter() - t0
    assert ncatch_proc == len(output)
    print(f"single thread -> {ncatch_proc} weights calculated in {tf:.1f}s for a rate of {ncatch_proc/tf:.1f}catch/s",flush=True)

    return output

def get_projection(raster_file):
    if 'https://' in raster_file:
        print(f"Downloading file...")
        response = requests.get(raster_file)
        
        if response.status_code == 200:
            raster_file = BytesIO(response.content)

    print(f"Opening raster",flush=True)
    try:
        raster_data = xr.open_dataset(raster_file)  
        print(f"Attemping Projection",flush=True)
        projection = raster_data.crs.esri_pe_string
        print("Projection successful")
    except:
        raster_backup = "https://noaa-nwm-retrospective-3-0-pds.s3.amazonaws.com/CONUS/netcdf/FORCING/2018/201801010000.LDASIN_DOMAIN1"
        if raster_backup == raster_file: raise Exception(f"Projection failed")
        print(f"No projection found in {raster_file}\nSwitching to template file: {raster_backup}")
        projection, raster_data = get_projection(raster_backup)

    return projection, raster_data


def calc_weights_from_gdf(gdf:gpd.GeoDataFrame, raster_file : str, nf :str) -> dict:
    # Create a dict of weights from the "divides" layer geodataframe
    # keys are divide_ids, values are a 2 element list 
    # with the first element being a list of cell_id's
    # and the second element being the corresponding coverage fraction's
    projection, raster_data = get_projection(raster_file)
    geo_data = gdf.to_crs(projection)   
    nrows = len(gdf) 
    
    nprocs = max(min(nrows // 9000 , (os.cpu_count()-1) // nf),1)
    geo_df_list = []
    nper = nrows // nprocs
    nleft = nrows - (nper * nprocs)   
    i = 0
    k = nper
    for j in range(nprocs):
        if j < nleft: k += 1
        print(f"{i} {k} {k-i}")
        geo_df_list.append(geo_data[i:k])
        i=k
        k = nper + i
        
    print(f"Performing multiprocess exactextract",flush=True)
    output_list = []
    raster_list = [raster_data for x in range (nprocs)]
    with cf.ProcessPoolExecutor(max_workers=nprocs) as pool:
        for results in pool.map(
            rastersourceNexactextract,
            raster_list,
            geo_df_list
            ):
            output_list.append(results)
    print(f"Concatenating results",flush=True)
    output = pd.concat(output_list, ignore_index=True)
    weights = output.set_index("divide_id")
    return weights

def multiprocess_hf2ds(files : list,raster_template : str, max_procs : int):

    nprocs = min(len(files),max_procs)
    nf = len(files)
    files_list = []
    nper = nf // nprocs
    nleft = nf - (nper * nprocs)   
    i = 0
    k = nper
    for j in range(nprocs):
        if j < nleft: k += 1
        files_list.append(files[i:k])
        i=k
        k = nper + i
        
    weight_dfs = []
    jcatchment_dicts = []
    with cf.ProcessPoolExecutor(max_workers=nprocs) as pool:
        for results in pool.map(
        hf2ds,
        files_list,
        [raster_template for x in range(len(files_list))],
        [nf for x in range(len(files_list))]
        ):
            weight_dfs.append(results[0])
            jcatchment_dicts.append(results[1])  

    weights_df = pd.concat(weight_dfs)

    print(f'Processes have returned',flush=True)
    jcatchment_dict = {}
    [jcatchment_dict.update(x) for x in jcatchment_dicts]
  
    return weights_df, jcatchment_dict  


def hf2ds(files : list, raster : str, nf):
    """
    Extracts the weights from a list of files

    input : files
    gpkg_files : list of geopackage or parquet files

    returns : weights_df, jcatchment_dict
    weights_df : a dataframe where index is catchment ids and the columns are the corresponding cell and coverage
    jcatchment_dict : A dictionary where the keys are the geopackage name and the values are a list of catchment id's

    """
    jcatchment_dict = {}
    count = 0
    for jgpkg in files:
        pattern = r"(?i)vpu[-_](\d+)"
        match = re.search(pattern, jgpkg)
        if match: jname = "VPU_" + match.group(1)
        else:
            count +=1
            jname = str(count)    
        weights_df = hydrofabric2datastream_weights(jgpkg,raster,nf)
        jcatchment_dict[jname] = list(weights_df.index)

    return weights_df, jcatchment_dict

def hydrofabric2datastream_weights(weights_file : str, raster_template: str, nf : int) -> dict:
    """
    Converts tabular weights to a dictionary where keys are catchment ids and the values are a list of weights
    
    input gpkg or path to weights parquet
    gpkg : gpd.Dataframe

    returns weights_json : a dictionary where keys are catchment ids and the values are a list of weights

    """
    # This function looks a bit wild bc weights may be provided 
    # to datastream in several different ways, or not at all. 
    # Need to handle each situation. 

    t0 = time.perf_counter()    

    if weights_file.endswith('.json'):
        with open(weights_file,'r') as fp:
            weights_json = json.load(fp)
        ncatchment = len(weights_json) 
        weights_df = pd.DataFrame.from_dict(weights_json, orient='index', columns=['cell_id','coverage'])
    else:
        if weights_file.endswith('.gpkg'):
            catchments     = gpd.read_file(weights_file, layer='divides')
            layers         = gpd.list_layers(weights_file)
            if 'forcing-weights' in list(layers.name):
                print(f'Weights table found in geopackage as \'forcing-weights\'. Converting to dict for processing.',flush=True)
                weights_df  = gpd.read_file(weights_file, layer = 'forcing-weights')
            else:
                print(f'Weights table not found in geopackage. Calculating from scratch with raster {raster_template}.',flush=True)
                weights_df = calc_weights_from_gdf(catchments,raster_template, nf)
                ncatchment = len(weights_df) 
        elif weights_file.endswith('parquet'):            
            weights_df = pd.read_parquet(weights_file)
            ncatchment = len(weights_df) 
        else:
            raise Exception(f'Dont know how to deal with {weights_file}')

        if "cell" in weights_df.columns:
            weights_table_unqiue_ids = weights_df.groupby('divide_id').agg(tuple).map(list).reset_index()
            weights_table_unqiue_ids = weights_table_unqiue_ids.set_index('divide_id')
            weights_df = weights_table_unqiue_ids.rename(columns={"cell":"cell_id"})
            weights_df['cell_id'] = weights_df['cell_id'].apply(lambda x: [int(i) for i in x])
            weights_df = weights_df.rename(columns={"coverage_fraction":"coverage"})
            ncatchment = len(weights_df) 

    tf = time.perf_counter()
    dt = tf - t0
    print(f'{weights_file} {ncatchment} catchment weights obtained {dt:.2f} seconds total, {ncatchment/dt:.2f} catchments/second',flush=True)
    return weights_df

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--input_file', dest="input_file", type=str, help="Path to geopackage or weights parquet file",default = None)
    parser.add_argument('--outname', dest="outname", type=str, help="Filename for the datastream weights file")
    args = parser.parse_args()

    global raster_template
    raster_template = "https://noaa-nwm-pds.s3.amazonaws.com/nwm.20250105/forcing_short_range/nwm.t00z.short_range.forcing.f001.conus.nc"

    weights, jcatchments = hf2ds(args.input_file.split(','))
    weights.to_parquet(args.outname)
    
