import pytest, os, json
import pandas as pd
from pathlib import Path
from datetime import datetime
import requests
from datetime import datetime

from forcingprocessor.processor import prep_ngen_data
from forcingprocessor.nwm_filenames_generator import generate_nwmfiles
from forcingprocessor.weights_parq2json import hydrofabric2datastream_weights

weight_name = "weights_poudre.json"

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

    os.system(f"hfsubset -w medium_range -s nextgen -v 2.1.1 -l divides,flowlines,network,nexus,forcing-weights,flowpath-attributes -o {pytest.data_dir}/palisade.gpkg -t hl \"Gages-09106150\"")

    weights = hydrofabric2datastream_weights(f"{pytest.data_dir}/palisade.gpkg")

    data = json.dumps(weights)
    with open(pytest.full_weight,'w') as fp:
        fp.write(data)    

    assert pytest.full_weight.exists()


def test_processor(get_time, get_paths):
    
    conf = {
    "forcing"  : {
        "nwm_file"   : str(pytest.filenamelist),
        "gpkg_file"  : str(f"{pytest.data_dir}/palisade.gpkg")
    },

    "storage":{
        "storage_type"      : "local",
        "output_path"       : str(pytest.data_dir),
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

            parquet = (pytest.data_dir/"forcings/cat-2586011.parquet").resolve()
            assert parquet.exists()
            os.remove(parquet)         


    
    
    
