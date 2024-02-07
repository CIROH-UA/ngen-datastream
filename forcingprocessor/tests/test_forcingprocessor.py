import pytest, os
import pandas as pd
from pathlib import Path
from datetime import datetime
import requests
from datetime import datetime

from forcingprocessor.forcingprocessor import prep_ngen_data
from forcingprocessor.nwm_filenames_generator import generate_nwmfiles
from forcingprocessor.weights_parq2json import get_weight_json

grid_filename   = "nwm.t00z.medium_range.forcing.f001.conus.nc"
geopkg_filename = "Gages-04185000.gpkg"
weight_name     = "Gages-04185000-weights.json"

geopkg_file     = f"https://ngenresourcesdev.s3.us-east-2.amazonaws.com/{geopkg_filename}"

@pytest.fixture()
def get_time():
    date = datetime.now()
    pytest.date = date.strftime('%Y%m%d')
    pytest.hourminute  = '0000'

@pytest.fixture()
def get_paths():
    test_dir = Path(__file__).parent
    data_dir = (test_dir/'data').resolve()
    pwd      = Path.cwd()
    pytest.pwd      = pwd
    pytest.data_dir = data_dir

    full_geo    = (data_dir/geopkg_filename).resolve()
    full_grid   = (data_dir/grid_filename).resolve()
    full_weight = (data_dir/weight_name).resolve()
    pytest.full_geo    = full_geo
    pytest.full_grid   = full_grid
    pytest.full_weight = full_weight

    pytest.filenamelist = (pwd/"filenamelist.txt").resolve()

def test_generate_filenames(get_paths, get_time):
    conf = {
    "forcing_type" : "operational_archive",
    "start_date"   : "",
    "end_date"     : "",
    "runinput"     : 1,
    "varinput"     : 5,
    "geoinput"     : 1,
    "meminput"     : 0,
    "urlbaseinput" : 7,
    "fcst_cycle"   : [0],
    "lead_time"    : [1,2]
}

    conf['start_date'] = pytest.date + pytest.hourminute
    conf['end_date']   = pytest.date + pytest.hourminute    
    generate_nwmfiles(conf)

    assert pytest.filenamelist.exists()

def test_generate_weights(get_paths):
    uri = "s3://lynker-spatial/v20.1/forcing_weights/forcing_weights_01.parquet"
    weights_df = pd.read_parquet(uri)
    catchment_list = list(weights_df.divide_id.unique())
    del weights_df        
    
    get_weight_json(catchment_list,0)
    assert pytest.full_weight.exists()

def test_processor(get_time, get_paths):
    
    conf = {

    "forcing"  : {
        "start_date"   : pytest.date + pytest.hourminute,
        "end_date"     : pytest.date + pytest.hourminute,
        "nwm_file"     : str(pytest.filenamelist),
        "weight_file"  : str(pytest.full_weight)
    },

    "storage":{
        "storage_type"      : "local",
        "output_bucket"     : pytest.date,
        "output_path"       : str(pytest.data_dir),
        "output_file_type"  : "csv"
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
    nwmurl_conf['start_date'] = pytest.date + pytest.hourminute
    nwmurl_conf['end_date']   = pytest.date + pytest.hourminute 
    
    for jurl in [1,2,3,5,6,7,8,9]:
        nwmurl_conf["urlbaseinput"] = jurl

        generate_nwmfiles(nwmurl_conf)

        with open(pytest.filenamelist,'r') as fp:            
            for jline in fp.readlines():                
                web_address = jline.strip()
                break

        if web_address.find('https://') >= 0:
            response = requests.get(web_address)
            if response.status_code != 200:
                print(f'{jline} doesn\'t exist!')
                pass
            else:
                print(f'{jline} exists! Testing with forcingprocessor')
                        
                prep_ngen_data(conf)

                tarball = (pytest.data_dir/pytest.date/"forcings/forcings.tar.gz").resolve()
                assert tarball.exists()
                os.remove(tarball)
        else:
            # in bucket, implement bucket checks for files
            pass


    
    
    