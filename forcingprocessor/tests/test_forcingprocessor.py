import os
from pathlib import Path
from datetime import datetime
from datetime import datetime
from forcingprocessor.processor import prep_ngen_data
from forcingprocessor.nwm_filenames_generator import generate_nwmfiles
import pytz as tz
import pytest

HF_VERSION="v2.1.1"
date = datetime.now(tz.timezone('US/Eastern'))
date = date.strftime('%Y%m%d')
hourminute  = '0000'
test_dir = Path(__file__).parent
data_dir = (test_dir/'data').resolve()
pwd      = Path.cwd()
pwd      = pwd
data_dir = data_dir
if os.path.exists(data_dir):
    os.system(f"rm -rf {data_dir}")
os.system(f"mkdir {data_dir}")
pwd      = Path.cwd()
filenamelist = str((pwd/"filenamelist.txt").resolve())
retro_filenamelist = str((pwd/"retro_filenamelist.txt").resolve())
geopackage_name = "palisade.gpkg"
os.system(f"curl -o {os.path.join(data_dir,geopackage_name)} -L -O https://ngen-datastream/palisade.gpkg")
weights_name = "01_weights.parquet"
os.system(f"curl -o {os.path.join(data_dir,weights_name)} -L -O https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/{HF_VERSION}/nextgen/conus_forcing-weights/vpuid%3D01/part-0.parquet")
assert_file=(data_dir/f"forcings/cat-2586011.parquet").resolve()

conf = {
    "forcing"  : {
        "nwm_file"   : filenamelist,
        "gpkg_file"  : str(f"{data_dir}/{geopackage_name}")
    },

    "storage":{
        "storage_type"      : "local",
        "output_path"       : str(data_dir),
        "output_file_type"  : ["parquet"]
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
    assert assert_file.exists()
    os.remove(assert_file)       

def test_gs():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 5
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    assert assert_file.exists()
    os.remove(assert_file)       

def test_gcs():
    nwmurl_conf['start_date'] = "202407100100"
    nwmurl_conf['end_date']   = "202407100100" 
    nwmurl_conf["urlbaseinput"] = 6
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    assert assert_file.exists()
    os.remove(assert_file)         

def test_noaa_nwm_pds_https():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 7
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    assert assert_file.exists()
    os.remove(assert_file)     

def test_noaa_nwm_pds_s3():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 8
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
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
    assert assert_file.exists()
    os.remove(assert_file)     

def test_retro_2_1_s3():
    conf['forcing']['nwm_file'] = retro_filenamelist
    nwmurl_conf_retro["urlbaseinput"] = 2
    generate_nwmfiles(nwmurl_conf_retro)
    prep_ngen_data(conf)
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
    GIF = (data_dir/"metadata/GIFs/T2D_2_TMP_2maboveground.gif").resolve()
    assert GIF.exists()
    os.remove(GIF)         

def test_s3_output():
    test_bucket = "ciroh-community-ngen-datastream"
    conf['forcing']['nwm_file'] = retro_filenamelist
    conf['storage']['storage_type'] = 's3'
    conf['storage']['output_path'] = f's3://{test_bucket}/pytest_fp/'
    nwmurl_conf_retro["urlbaseinput"] = 4
    generate_nwmfiles(nwmurl_conf_retro)
    prep_ngen_data(conf)   
    os.system(f"aws s3api wait object-exists --bucket {test_bucket} --key {test_bucket}/pytest_fp/forcings/1_forcings.nc")
    os.system(f"aws s3api delete-object --bucket {test_bucket} --key {test_bucket}/pytest_fp/forcings/1_forcings.nc")   
    conf['storage']['storage_type'] = 'local'
    conf['storage']['output_path'] = str(data_dir)

def test_muliple_weights():
    conf['forcing']['nwm_file'] = retro_filenamelist
    nwmurl_conf_retro["urlbaseinput"] = 4
    conf['forcing']['gpkg_file'] = ["https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/v2.1.1/nextgen/conus_forcing-weights/vpuid%3D01/part-0.parquet","https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/v2.1.1/nextgen/conus_forcing-weights/vpuid%3D02/part-0.parquet"]
    generate_nwmfiles(nwmurl_conf_retro)
    prep_ngen_data(conf)   

    
