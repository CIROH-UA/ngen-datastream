import pytest, os, json
import pandas as pd
from pathlib import Path
from datetime import datetime
import requests
from datetime import datetime

from forcingprocessor.forcingprocessor import prep_ngen_data
from forcingprocessor.nwm_filenames_generator import generate_nwmfiles
from forcingprocessor.weights_parq2json import get_weight_json, get_catchments_from_gpkg

weight_name = "weights_01.json"

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
    os.system(f"mkdir {data_dir}")

    full_weight = (data_dir/weight_name).resolve()
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

    weights = get_weight_json(["cat-1","cat-10","cat-100","cat-1000","cat-10000","cat-100000"],"v20.1",os.cpu_count())

    data = json.dumps(weights)
    with open(pytest.full_weight,'w') as fp:
        fp.write(data)    

    assert pytest.full_weight.exists()

    os.system('curl -L -O https://lynker-spatial.s3.amazonaws.com/hydrofabric/v20.1/gpkg/nextgen_09.gpkg')

    get_catchments_from_gpkg('./nextgen_09.gpkg')


def test_processor(get_time, get_paths):
    
    conf = {
    "forcing"  : {
        "nwm_file"     : str(pytest.filenamelist),
        "weight_file"  : str(pytest.full_weight)
    },

    "storage":{
        "output_path"       : str(pytest.data_dir),
        "output_file_type"  : ["tar","parquet","netcdf"]
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
    
    for jurl in [1,3,5,6,7,8]:
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
                raise Exception
            print(f'{jline} exists! Testing with forcingprocessor')
                    
            prep_ngen_data(conf)

            tarball = (pytest.data_dir/"forcings/1_forcings.tar.gz").resolve()
            assert tarball.exists()
            os.remove(tarball)

            parquet = (pytest.data_dir/"forcings/cat-1.parquet").resolve()
            assert parquet.exists()
            os.remove(parquet)

            # nc = (pytest.data_dir/"forcings/1_forcings.nc").resolve()
            # assert nc.exists()    
            # os.remove(nc)            


    
    
    
