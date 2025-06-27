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
DATA_DIR = (test_dir/'data').resolve()
pwd      = Path.cwd()
filenamelist = str((pwd/"filenamelist.txt").resolve())
geopackage_name = "vpu-09_subset.gpkg"
geopackage = str(f"{DATA_DIR}/{geopackage_name}")
if os.path.exists(DATA_DIR):
    os.system(f"rm -rf {DATA_DIR}")
os.system(f"mkdir {DATA_DIR}")


os.system(f"curl -o {os.path.join(DATA_DIR,geopackage_name)} -L -O https://datastream-resources.s3.us-east-1.amazonaws.com/VPU_09/config/nextgen_VPU_09.gpkg")

conf = {
    "forcing"  : {
        "nwm_file"   : filenamelist,
        "gpkg_file"  : [geopackage]
    },

    "storage":{
        "output_path"       : str(DATA_DIR),
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

# @pytest.fixture
# def clean_dir(autouse=True):
#     if os.path.exists(DATA_DIR):
#         os.system(f'rm -rf {str(DATA_DIR)}')
#     os.system(f'mkdir {str(DATA_DIR)}')

def test_forcings_plot():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 7    

    generate_nwmfiles(nwmurl_conf)
    prep_ngen_data(conf)

    nwm_dir = os.path.join(DATA_DIR,'nwm_forcings')
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

    forcings_nc = os.path.join(DATA_DIR,"forcings/ngen.t00z.short_range.forcing.f001_f001.VPU_09.nc")
    ngen_data, t_ax, catchment_ids = nc_to_3darray(forcings_nc)            

    plot_ngen_forcings(
        nwm_data, 
        ngen_data, 
        geopackage, 
        t_ax, 
        catchment_ids,
        ["TMP_2maboveground"],
        os.path.join(DATA_DIR,'metadata/GIFs')
        )
    
    os.remove(forcings_nc)
    os.system(f'rm -rf {str(DATA_DIR)}forcings/*.parquet')
    ngen_data, t_ax, catchment_ids = csvs_to_3darray(os.path.join(DATA_DIR,'forcings')) 
    plot_ngen_forcings(
        nwm_data, 
        ngen_data, 
        geopackage, 
        t_ax, 
        catchment_ids,
        ["TMP_2maboveground"],
        os.path.join(DATA_DIR,'metadata/GIFs')
        )
