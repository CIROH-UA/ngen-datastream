import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from forcingprocessor.processor import prep_ngen_data
from forcingprocessor.nwm_filenames_generator import generate_nwmfiles
import pytest
import re

HF_VERSION="v2.2"
date = datetime.now(timezone.utc)
date = date.strftime('%Y%m%d')
hourminute  = '0000'
yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
yesterday = yesterday.strftime('%Y%m%d')
test_dir = Path(__file__).parent
data_dir = (test_dir/'data').resolve()
forcings_dir = (data_dir/'forcings').resolve()
pwd      = Path.cwd()
pwd      = pwd
data_dir = data_dir
if os.path.exists(data_dir):
    os.system(f"rm -rf {data_dir}")
os.system(f"mkdir {data_dir}")
pwd      = Path.cwd()
filenamelist = str((pwd/"filenamelist.txt").resolve())
retro_filenamelist = str((pwd/"retro_filenamelist.txt").resolve())
geopackage_name = "vpu-09_subset.gpkg"
os.system(f"curl -o {os.path.join(data_dir,geopackage_name)} -L -O https://datastream-resources.s3.us-east-1.amazonaws.com/VPU_09/config/nextgen_VPU_09.gpkg")
assert_file=(data_dir/f"forcings/VPU_09_forcings.nc").resolve()

conf = {
    "forcing"  : {
        "nwm_file"   : filenamelist,
        "gpkg_file"  : str(f"{data_dir}/{geopackage_name}")
    },

    "storage":{
        "storage_type"      : "local",
        "output_path"       : str(data_dir),
        "output_file_type"  : ["netcdf"]
    },    

    "run" : {
        "verbose"       : False,
        "collect_stats" : False,
        "nprocs"         : 1
    }
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

nwmurl_conf_retro = {
        "forcing_type" : "retrospective",
        "start_date"   : "201801010000",
        "end_date"     : "201801010000",
        "urlbaseinput" : 1,
        "selected_object_type" : [1],
        "selected_var_types"   : [6],
        "write_to_file" : True
    }

@pytest.fixture
def clean_dir(autouse=True):
    if os.path.exists(forcings_dir):
        os.system(f'rm -rf {str(forcings_dir)}')

def test_nomads_prod():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 1
    generate_nwmfiles(nwmurl_conf)  
    conf['run']['collect_stats'] = True # test metadata generation once
    prep_ngen_data(conf)
    conf['run']['collect_stats'] = False
    assert assert_file.exists()
    os.remove(assert_file)       

def test_nomads_post_processed():
    assert False, f'test_nomads_post_processed() is BROKEN - https://github.com/CIROH-UA/nwmurl/issues/62'
    nwmurl_conf['start_date'] = "202408240000"
    nwmurl_conf['end_date']   = "202408241700"
    nwmurl_conf["urlbaseinput"] = 2
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    assert assert_file.exists()
    os.remove(assert_file)    

def test_nwm_google_apis():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 3
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    assert assert_file.exists()
    os.remove(assert_file)       

def test_google_cloud_storage():
    nwmurl_conf['start_date'] = "202407100100"
    nwmurl_conf['end_date']   = "202407100100" 
    nwmurl_conf["urlbaseinput"] = 4
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    assert_file=(data_dir/f"forcings/ngen.t00z.short_range.forcing.f001_f001.VPU_09.nc").resolve()
    assert assert_file.exists()
    os.remove(assert_file)       

def test_gs():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 5
    generate_nwmfiles(nwmurl_conf)   
    assert_file=(data_dir/f"forcings/ngen.t00z.short_range.forcing.f001_f001.VPU_09.nc").resolve()       
    prep_ngen_data(conf)
    assert assert_file.exists()
    os.remove(assert_file)       

def test_gcs():
    nwmurl_conf['start_date'] = "202407100100"
    nwmurl_conf['end_date']   = "202407100100" 
    nwmurl_conf["urlbaseinput"] = 6
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    assert_file=(data_dir/f"forcings/ngen.t00z.short_range.forcing.f001_f001.VPU_09.nc").resolve()
    assert assert_file.exists()
    os.remove(assert_file)         

def test_noaa_nwm_pds_https():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 7
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    assert_file=(data_dir/f"forcings/ngen.t00z.short_range.forcing.f001_f001.VPU_09.nc").resolve()
    assert assert_file.exists()
    os.remove(assert_file)     

def test_noaa_nwm_pds_https_short_range():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 7
    nwmurl_conf["runinput"] = 1
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    assert_file=(data_dir/f"forcings/ngen.t00z.short_range.forcing.f001_f001.VPU_09.nc").resolve()
    assert assert_file.exists()
    os.remove(assert_file) 

def test_noaa_nwm_pds_https_medium_range():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 7
    nwmurl_conf["runinput"] = 2
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    assert_file=(data_dir/f"forcings/ngen.t00z.medium_range.forcing.f001_f001.VPU_09.nc").resolve()
    assert assert_file.exists()
    os.remove(assert_file)         

def test_noaa_nwm_pds_https_analysis_assim():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 7
    nwmurl_conf["runinput"] = 5
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    assert_file=(data_dir/f"forcings/ngen.t00z.analysis_assim.forcing.tm01_tm01.VPU_09.nc").resolve()
    assert assert_file.exists()
    os.remove(assert_file)  

def test_noaa_nwm_pds_https_analysis_assim_extend():
    nwmurl_conf['start_date'] = yesterday + hourminute
    nwmurl_conf['end_date']   = yesterday + hourminute    
    nwmurl_conf["urlbaseinput"] = 7
    nwmurl_conf["runinput"] = 6
    nwmurl_conf["fcst_cycle"] = [16]
    generate_nwmfiles(nwmurl_conf)       
    try:   
        prep_ngen_data(conf)
    except Exception as e:
        pattern = r"https://noaa-nwm-pds\.s3\.amazonaws\.com/nwm\.\d{8}/forcing_analysis_assim_extend/nwm\.t16z\.analysis_assim_extend\.forcing\.tm01\.conus\.nc does not exist"
        if re.fullmatch(pattern, str(e)):
            pytest.skip(f"Upstream datafile missing: {e}")
        else:
            raise
    assert_file=(data_dir/f"forcings/ngen.t16z.analysis_assim_extend.forcing.tm01_tm01.VPU_09.nc").resolve()
    assert assert_file.exists()
    os.remove(assert_file)    

def test_noaa_nwm_pds_s3():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute   
    nwmurl_conf["runinput"] = 1 
    nwmurl_conf["urlbaseinput"] = 8
    nwmurl_conf["fcst_cycle"] = [0]
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    assert_file=(data_dir/f"forcings/ngen.t00z.short_range.forcing.f001_f001.VPU_09.nc").resolve()
    assert assert_file.exists()
    os.remove(assert_file)            

def test_ciroh_zarr():
    assert False, "Not implemented"
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 9
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    assert assert_file.exists()
    os.remove(assert_file)        

def test_retro_2_1_https():
    conf['forcing']['nwm_file'] = retro_filenamelist
    nwmurl_conf_retro["urlbaseinput"] = 1
    generate_nwmfiles(nwmurl_conf_retro)
    prep_ngen_data(conf)
    assert_file=(data_dir/f"forcings/VPU_09_forcings.nc").resolve()
    assert assert_file.exists()
    os.remove(assert_file)     

def test_retro_2_1_s3():
    conf['forcing']['nwm_file'] = retro_filenamelist
    nwmurl_conf_retro["urlbaseinput"] = 2
    generate_nwmfiles(nwmurl_conf_retro)
    prep_ngen_data(conf)
    assert_file=(data_dir/f"forcings/VPU_09_forcings.nc").resolve()
    assert assert_file.exists()
    os.remove(assert_file)               

def test_retro_ciroh_zarr():
    assert False, "Not implemented"
    conf['forcing']['nwm_file'] = retro_filenamelist
    nwmurl_conf_retro["urlbaseinput"] = 3
    generate_nwmfiles(nwmurl_conf_retro)
    prep_ngen_data(conf)
    assert assert_file.exists()
    os.remove(assert_file)          

def test_retro_3_0():
    conf['forcing']['nwm_file'] = retro_filenamelist
    nwmurl_conf_retro["urlbaseinput"] = 4
    generate_nwmfiles(nwmurl_conf_retro)
    prep_ngen_data(conf)
    assert_file=(data_dir/f"forcings/VPU_09_forcings.nc").resolve()
    assert assert_file.exists()
    os.remove(assert_file)          

def test_plotting():
    conf['forcing']['nwm_file'] = retro_filenamelist
    conf['plot'] = {}
    conf['plot']['nts'] = 1
    conf['plot']['ngen_vars'] = [
            "TMP_2maboveground"
        ] 
    nwmurl_conf_retro["urlbaseinput"] = 4
    generate_nwmfiles(nwmurl_conf_retro)
    prep_ngen_data(conf)
    del conf['plot']
    GIF = (data_dir/"metadata/GIFs/T2D_2_TMP_2maboveground.gif").resolve()
    assert GIF.exists()
    os.remove(GIF)         

def test_s3_output():
    test_bucket = "ciroh-community-ngen-datastream"
    conf['forcing']['nwm_file'] = retro_filenamelist
    conf['storage']['output_path'] = f's3://{test_bucket}/pytest_fp'
    conf['storage']['output_file_type'] = ["netcdf"]
    nwmurl_conf_retro["urlbaseinput"] = 4
    generate_nwmfiles(nwmurl_conf_retro)
    prep_ngen_data(conf)     
    conf['storage']['output_path'] = str(data_dir)
    os.system(f'aws s3api delete-object --bucket {test_bucket} --key pytest_fp/VPU_09_forcings.nc')
    os.system(f'aws s3api delete-object --bucket {test_bucket} --key pytest_fp/metadata/forcings_metadata/conf_fp.json')
    os.system(f'aws s3api delete-object --bucket {test_bucket} --key pytest_fp/metadata/forcings_metadata/retro_filenamelist.txt')
    os.system(f'aws s3api delete-object --bucket {test_bucket} --key pytest_fp/metadata/forcings_metadata/profile_fp.txt')
    os.system(f'aws s3api delete-object --bucket {test_bucket} --key pytest_fp/metadata/forcings_metadata/weights.parquet')

def test_csv_output_type():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute   
    nwmurl_conf["runinput"] = 1 
    nwmurl_conf["urlbaseinput"] = 8
    nwmurl_conf["fcst_cycle"] = [0]
    generate_nwmfiles(nwmurl_conf)  
    conf['storage']['output_file_type'] = ["csv"]      
    prep_ngen_data(conf)
    assert_file=(data_dir/f"forcings/cat-1496145.csv").resolve()
    assert assert_file.exists()
    os.remove(assert_file)   

def test_parquet_output_type():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute   
    nwmurl_conf["runinput"] = 1 
    nwmurl_conf["urlbaseinput"] = 8
    nwmurl_conf["fcst_cycle"] = [0]
    generate_nwmfiles(nwmurl_conf)  
    conf['storage']['output_file_type'] = ["parquet"]      
    prep_ngen_data(conf)
    assert_file=(data_dir/f"forcings/cat-1496145.parquet").resolve()
    assert assert_file.exists()
    os.remove(assert_file)        


    
