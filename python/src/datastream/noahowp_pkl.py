from pathlib import Path
import re, copy, pickle, argparse
import pandas as pd

def gen_noah_owp_pkl(attrs_path,out):
    print(f'Generating NoahOWP pkl',flush=True)
    template = Path(__file__).parent.parent.parent.parent/"configs/ngen/noah-owp-modular-init.namelist.input"
    with open(template,'r') as fp:
        conf_template = fp.readlines()
    
    attrs     = pd.read_parquet(attrs_path)
    catchment_list = sorted(list(attrs['divide_id']))

    all_confs = {}
    for jcatch in catchment_list:
        jcatch_conf = copy.deepcopy(conf_template)
        jcatch_attrs = attrs.loc[attrs["divide_id"] == jcatch]
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

    with open(Path(out,"noah-owp-modular-init.namelist.input.pkl"),'wb') as fp:
        pickle.dump(all_confs, fp, protocol=pickle.HIGHEST_PROTOCOL)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hf_lnk_file",
        dest="hf_lnk_file", 
        type=str,
        help="Path to the .gpkg attributes", 
        required=False
    )
    parser.add_argument(
        "--outdir",
        dest="outdir", 
        type=str,
        help="Path to the .gpkg attributes", 
        required=False
    )    

    args = parser.parse_args()

    if '.txt' in args.hf_lnk_file:
        with open(args.hf_lnk_file,'r') as fp:
            data=fp.readlines()
            hf_lnk_file = data[0] 
    else:
        hf_lnk_file = args.hf_lnk_file

    gen_noah_owp_pkl(hf_lnk_file,args.outdir)        