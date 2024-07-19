import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from datetime import datetime
from forcingprocessor.processor import prep_ngen_data
from forcingprocessor.nwm_filenames_generator import generate_nwmfiles

date = datetime.now()
date = date.strftime('%Y%m%d')
hourminute  = '0000'
test_dir = Path(__file__).parent
data_dir = (test_dir/'data').resolve()
pwd      = Path.cwd()
pwd      = pwd
data_dir = data_dir
os.system(f"mkdir {data_dir}")
pwd      = Path.cwd()
filenamelist = str((pwd/"filenamelist.txt").resolve())
retro_filenamelist = str((pwd/"retro_filenamelist.txt").resolve())

conf = {
    "forcing"  : {
        "nwm_file"   : filenamelist,
        "gpkg_file"  : str(f"{data_dir}/palisade.gpkg")
    },

    "storage":{
        "storage_type"      : "local",
        "output_path"       : str(data_dir),
        "output_file_type"  : ["parquet"]
    },    

    "run" : {
        "verbose"       : False,
        "collect_stats" : True
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
    prep_ngen_data(conf)
    parquet = (data_dir/"forcings/cat-2586011.parquet").resolve()
    assert parquet.exists()
    os.remove(parquet)       

def test_nomads_post_processed():
    nwmurl_conf['start_date'] = "202407170000"
    nwmurl_conf['end_date']   = "202407170000"
    nwmurl_conf["urlbaseinput"] = 2
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    parquet = (data_dir/"forcings/cat-2586011.parquet").resolve()
    assert parquet.exists()
    os.remove(parquet)  

def test_nwm_google_apis():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 3
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    parquet = (data_dir/"forcings/cat-2586011.parquet").resolve()
    assert parquet.exists()
    os.remove(parquet)          

def test_google_cloud_storage():
    assert False # hangs in pytest, but should work
    nwmurl_conf['start_date'] = "202407100100"
    nwmurl_conf['end_date']   = "202407100100" 
    nwmurl_conf["urlbaseinput"] = 4
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    parquet = (data_dir/"forcings/cat-2586011.parquet").resolve()
    assert parquet.exists()
    os.remove(parquet)   

def test_gs_nwm():
    assert False # hangs in pytest, but should work
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 5
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    parquet = (data_dir/"forcings/cat-2586011.parquet").resolve()
    assert parquet.exists()
    os.remove(parquet)       

def test_gcs_nwm():
    assert False # hangs in pytest, but should work
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 6
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    parquet = (data_dir/"forcings/cat-2586011.parquet").resolve()
    assert parquet.exists()
    os.remove(parquet)    

def test_noaa_nwm_pds():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 7
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    parquet = (data_dir/"forcings/cat-2586011.parquet").resolve()
    assert parquet.exists()
    os.remove(parquet)      

def test_noaa_nwm_pds_s3():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 8
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    parquet = (data_dir/"forcings/cat-2586011.parquet").resolve()
    assert parquet.exists()
    os.remove(parquet)     

def test_ciroh_zarr():
    nwmurl_conf['start_date'] = date + hourminute
    nwmurl_conf['end_date']   = date + hourminute    
    nwmurl_conf["urlbaseinput"] = 9
    generate_nwmfiles(nwmurl_conf)          
    prep_ngen_data(conf)
    parquet = (data_dir/"forcings/cat-2586011.parquet").resolve()
    assert parquet.exists()
    os.remove(parquet)     

def test_retro_2_1():
    conf['forcing']['nwm_file'] = retro_filenamelist
    nwmurl_conf_retro["urlbaseinput"] = 1
    generate_nwmfiles(nwmurl_conf_retro)
    prep_ngen_data(conf)
    parquet = (data_dir/"forcings/cat-2586011.parquet").resolve()
    assert parquet.exists()
    os.remove(parquet)  

def test_retro_2_1_s3():
    conf['forcing']['nwm_file'] = retro_filenamelist
    nwmurl_conf_retro["urlbaseinput"] = 2
    generate_nwmfiles(nwmurl_conf_retro)
    prep_ngen_data(conf)
    parquet = (data_dir/"forcings/cat-2586011.parquet").resolve()
    assert parquet.exists()
    os.remove(parquet)            

def test_retro_ciroh_zarr():
    conf['forcing']['nwm_file'] = retro_filenamelist
    nwmurl_conf_retro["urlbaseinput"] = 3
    generate_nwmfiles(nwmurl_conf_retro)
    prep_ngen_data(conf)
    parquet = (data_dir/"forcings/cat-2586011.parquet").resolve()
    assert parquet.exists()
    os.remove(parquet)         

def test_retro_3_0():
    conf['forcing']['nwm_file'] = retro_filenamelist
    nwmurl_conf_retro["urlbaseinput"] = 4
    generate_nwmfiles(nwmurl_conf_retro)
    prep_ngen_data(conf)
    parquet = (data_dir/"forcings/cat-2586011.parquet").resolve()
    assert parquet.exists()
    os.remove(parquet)        


    
    
    
