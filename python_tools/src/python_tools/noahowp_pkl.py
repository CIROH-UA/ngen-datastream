from pathlib import Path
import re, copy, pickle, argparse, os
import geopandas as gpd
gpd.options.io_engine = "pyogrio"
import concurrent.futures as cf

def gen_noah_owp_pkl(gdf):    
    template = Path(__file__).parent.parent.parent.parent/"configs/ngen/noah-owp-modular-init.namelist.input"
    with open(template,'r') as fp:
        conf_template = fp.readlines()

    all_confs = {}
    if HF_VERSION == "v2.2":
        for row in gdf.itertuples():
            jcatch = row.divide_id
            lat = row.centroid_x
            lon = row.centroid_y
            slope = row._37
            azimuth = row._38
            jcatch_conf = copy.deepcopy(conf_template)
            for j,jline in enumerate(jcatch_conf):
                pattern = r'^\s{2}lat\s*=\s*([\d.]+)\s*'
                if re.search(pattern,jline):
                    jcatch_conf[j] = re.sub(pattern,  f"  lat             = {lat}      ", jline)
                pattern =  r'^\s{2}lon\s*=\s*([\d.]+)\s*'
                if re.search(pattern,jline):                
                    jcatch_conf[j] =  re.sub(pattern, f"  lon             = {lon}      ", jline)
                pattern =  r'^\s{2}terrain_slope\s*=\s*([\d.]+)\s*'
                if re.search(pattern,jline):                
                    jcatch_conf[j] = re.sub(pattern,  f"  terrain_slope   = {slope}      ", jline)  
                pattern =  r'^\s{2}azimuth\s*=\s*([\d.]+)\s*'
                if re.search(pattern,jline):                
                    jcatch_conf[j] = re.sub(pattern,  f"  azimuth         = {azimuth}      ", jline) 

            all_confs[jcatch] = jcatch_conf
    else:
        catchment_list = sorted(list(gdf['divide_id']))        
        for jcatch in catchment_list:
            jcatch_conf = copy.deepcopy(conf_template)
            jcatch_attrs = gdf.loc[gdf["divide_id"] == jcatch]
            lat = jcatch_attrs["Y"].iloc[0]
            lon = jcatch_attrs["X"].iloc[0]
            slope = jcatch_attrs["slope_mean"].iloc[0]
            azimuth = jcatch_attrs["aspect_c_mean"].iloc[0]
            for j,jline in enumerate(jcatch_conf):
                pattern = r'^\s{2}lat\s*=\s*([\d.]+)\s*'
                if re.search(pattern,jline):
                    jcatch_conf[j] = re.sub(pattern,  f"  lat             = {lat}      ", jline)
                pattern =  r'^\s{2}lon\s*=\s*([\d.]+)\s*'
                if re.search(pattern,jline):                
                    jcatch_conf[j] =  re.sub(pattern, f"  lon             = {lon}      ", jline)
                pattern =  r'^\s{2}terrain_slope\s*=\s*([\d.]+)\s*'
                if re.search(pattern,jline):                
                    jcatch_conf[j] = re.sub(pattern,  f"  terrain_slope   = {slope}      ", jline)  
                pattern =  r'^\s{2}azimuth\s*=\s*([\d.]+)\s*'
                if re.search(pattern,jline):                
                    jcatch_conf[j] = re.sub(pattern,  f"  azimuth         = {azimuth}      ", jline)         

            all_confs[jcatch] = jcatch_conf
    return all_confs

def multiprocess_pkl(gpkg_path,outdir):
    print(f'Generating NoahOWP pkl',flush=True)

    global HF_VERSION
    try:
        HF_VERSION = "v2.2"
        gdf = gpd.read_file(gpkg_path,layer = 'divide-attributes').sort_values(by='divide_id')
    except:
        HF_VERSION = "v2.1"
        gdf = gpd.read_file(gpkg_path,layer = 'model-attributes').sort_values(by='divide_id')
    
    catchment_list = sorted(list(gdf['divide_id']))

    nprocs = max(os.cpu_count() - 1,1)
    ncatch = len(catchment_list)
    catchment_list_list = []
    gdf_list = []
    nper = ncatch // nprocs
    nleft = ncatch - (nper * nprocs)   
    i = 0
    k = nper
    for j in range(nprocs):
        if j < nleft: k += 1
        gdf_list.append(gdf[i:k])
        i=k
        k = nper + i
        
    all_proc_confs = {}
    with cf.ProcessPoolExecutor(max_workers=nprocs) as pool:
        for results in pool.map(
        gen_noah_owp_pkl,
        gdf_list
        ):
            all_proc_confs.update(results)

    if not os.path.exists(outdir): 
        os.system(f"mkdir -p {outdir}")
    with open(Path(outdir,"noah-owp-modular-init.namelist.input.pkl"),'wb') as fp:
        pickle.dump(all_proc_confs, fp, protocol=pickle.HIGHEST_PROTOCOL)        

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hf_file",
        dest="hf_file", 
        type=str,
        help="Path to the .gpkg", 
        required=False
    )
    parser.add_argument(
        "--outdir",
        dest="outdir", 
        type=str,
        help="Directory to write file out to", 
        required=False
    )    

    args = parser.parse_args()

    if '.txt' in args.hf_file:
        with open(args.hf_file,'r') as fp:
            data=fp.readlines()
            hf_file = data[0] 
    else:
        hf_file = args.hf_file

    outdir = args.outdir
    multiprocess_pkl(hf_file,outdir)   
    # gdf     = gpd.read_file(hf_file,layer = 'divide-attributes')
    # catchment_list = sorted(list(gdf['divide_id']))         
    # gen_noah_owp_pkl(catchment_list,gdf)