import os
from pathlib import Path
from datetime import datetime
from datetime import datetime
from forcingprocessor.processor import prep_ngen_data
from forcingprocessor.plot_forcings import nc_to_3darray, plot_ngen_forcings, csvs_to_3darray, get_nwm_data_array
from forcingprocessor.nwm_filenames_generator import generate_nwmfiles
import requests

date = datetime.now()
date = date.strftime('%Y%m%d')
hourminute  = '0000'
test_dir = Path(__file__).parent
data_dir = (test_dir/'data').resolve()
if os.path.exists(data_dir):
    os.system(f"rm -rf {data_dir}")
os.system(f"mkdir {data_dir}")
pwd      = Path.cwd()
filenamelist = str((pwd/"filenamelist.txt").resolve())
geopackage = str(f"{data_dir}/palisade.gpkg")
geopackage_name = "palisade.gpkg"
os.system(f"curl -o {os.path.join(data_dir,geopackage_name)} -L -O https://ngen-datastream.s3.us-east-2.amazonaws.com/{geopackage_name}")

conf = {
    "forcing"  : {
        "nwm_file"   : filenamelist,
        "gpkg_file"  : geopackage
    },

    "storage":{
        "storage_type"      : "local",
        "output_path"       : str(data_dir),
        "output_file_type"  : ["netcdf","csv"]
    },    

    "run" : {
        "verbose"       : False,
        "collect_stats" : True,
        "nproc"         : 8
    }
    }

nwmurl_conf_retro = {
        "forcing_type" : "retrospective",
        "start_date"   : "201801010000",
        "end_date"     : "201801012300",
        "urlbaseinput" : 1,
        "selected_object_type" : [1],
        "selected_var_types"   : [6],
        "write_to_file" : True
    }

nwmurl_conf = {
        "forcing_type" : "operational_archive",
        "start_date"   : "",
        "end_date"     : "",
        "runinput"     : 1,
        "varinput"     : 5,
        "geoinput"     : 1,
        "meminput"     : 0,
        "urlbaseinput" : 7,
        "fcst_cycle"   : [0],
        "lead_time"    : [1]
    }

def test_forcings_plot():
    os.system(f"mkdir {data_dir}")
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 7    
    generate_nwmfiles(nwmurl_conf)
    prep_ngen_data(conf)

    nwm_dir = os.path.join(data_dir,'nwm_forcings')
    if not os.path.exists(nwm_dir):
        os.system(f"mkdir {nwm_dir}")    
    
    filenamelist_file = "./filenamelist.txt"
    with open(filenamelist_file,'r') as fp:
        urls = fp.readlines()
        for jurl in urls:
            response = requests.get(jurl.strip())
            file_Path = os.path.join(nwm_dir,os.path.basename(jurl.strip()))
        if response.status_code == 200:
            with open(file_Path, 'wb') as file:
                file.write(response.content)
            print('File downloaded successfully')
        else:
            raise Exception(f'Failed to download file')

    nwm_data = get_nwm_data_array(nwm_dir,geopackage)             

    forcings_nc = os.path.join(data_dir,"forcings/1_forcings.nc")
    ngen_data, t_ax, catchment_ids = nc_to_3darray(forcings_nc)            

    plot_ngen_forcings(
        nwm_data, 
        ngen_data, 
        geopackage, 
        t_ax, 
        catchment_ids,
        ["TMP_2maboveground"],
        os.path.join(data_dir,'metadata/GIFs')
        )
    
    os.system(f'rm {forcings_nc}')
    ngen_data, t_ax, catchment_ids = csvs_to_3darray(os.path.join(data_dir,'forcings')) 
    plot_ngen_forcings(
        nwm_data, 
        ngen_data, 
        geopackage, 
        t_ax, 
        catchment_ids,
        ["TMP_2maboveground"],
        os.path.join(data_dir,'metadata/GIFs')
        )