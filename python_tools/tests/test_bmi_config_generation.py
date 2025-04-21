import pytest, os
from python_tools.ngen_configs_gen import gen_noah_owp_confs_from_pkl, gen_petAORcfe, generate_troute_conf
from python_tools.noahowp_pkl import multiprocess_pkl
import datetime as dt

TEST_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.path.join(TEST_DIR,'data')
if os.path.exists(DATA_DIR):
    os.system(f'rm -rf {str(DATA_DIR)}')
os.system(f'mkdir {str(DATA_DIR)}')
CONF_DIR = os.path.join(DATA_DIR,'cat_config')
NOAH_DIR = os.path.join(CONF_DIR,'NOAH-OWP-M')
CFE_DIR  = os.path.join(CONF_DIR,'CFE')
PET_DIR  = os.path.join(CONF_DIR,'PET')
GEOPACKAGE_NAME_v21 = "palisade.gpkg"
GEOPACKAGE_NAME_v22 = "vpu-09_subset.gpkg"
GEOPACKAGE_PATH_v21 = os.path.join(DATA_DIR,GEOPACKAGE_NAME_v21)
GEOPACKAGE_PATH_v22 = os.path.join(DATA_DIR,GEOPACKAGE_NAME_v22)
os.system(f"curl -o {GEOPACKAGE_PATH_v21} -L -O https://ngen-datastream.s3.us-east-2.amazonaws.com/{GEOPACKAGE_NAME_v21}")
os.system(f"curl -o {GEOPACKAGE_PATH_v22} -L -O https://communityhydrofabric.s3.us-east-1.amazonaws.com/hydrofabrics/community/VPU/{GEOPACKAGE_NAME_v22}")



PKL_FILE = os.path.join(DATA_DIR,"noah-owp-modular-init.namelist.input.pkl")
START    = dt.datetime.strptime("202006200100",'%Y%m%d%H%M')
END      = dt.datetime.strptime("202006200100",'%Y%m%d%H%M')


@pytest.fixture(autouse=True)
def clean_dir():
    if os.path.exists(CONF_DIR):
        os.system(f'rm -rf {str(CONF_DIR)}')
    os.system(f'mkdir {str(CONF_DIR)}')

def test_pkl_v21():
    multiprocess_pkl(GEOPACKAGE_PATH_v21,DATA_DIR)
    assert os.path.exists(PKL_FILE)

def test_noah_owp_m_v21():
    os.system(f'mkdir -p {NOAH_DIR}')
    gen_noah_owp_confs_from_pkl(PKL_FILE, NOAH_DIR, START, END)
    noah_config_example = os.path.join(NOAH_DIR,"noah-owp-modular-init-cat-2586011.namelist.input")
    assert os.path.exists(noah_config_example)

def test_cfe_v21():
    os.system(f'mkdir -p {CFE_DIR}')
    gen_petAORcfe(GEOPACKAGE_PATH_v21,DATA_DIR,["CFE"])
    cfe_example = os.path.join(CFE_DIR,"CFE_cat-2586011.ini")
    assert os.path.exists(cfe_example)

def test_pet_v21():
    os.system(f'mkdir -p {PET_DIR}')
    gen_petAORcfe(GEOPACKAGE_PATH_v21,DATA_DIR,["PET"])
    pet_example = os.path.join(PET_DIR,"PET_cat-2586011.ini")
    assert os.path.exists(pet_example)    

def test_routing_v21():
    max_loop_size = (END - START + dt.timedelta(hours=1)).total_seconds() / (3600)
    generate_troute_conf(DATA_DIR,START,max_loop_size,GEOPACKAGE_PATH_v21) 
    yml_example = os.path.join(DATA_DIR,'troute.yaml')
    assert os.path.exists(yml_example)



def test_pkl_v22():
    multiprocess_pkl(GEOPACKAGE_PATH_v22,DATA_DIR)
    assert os.path.exists(PKL_FILE)

def test_noah_owp_m_v22():
    os.system(f'mkdir -p {NOAH_DIR}')
    gen_noah_owp_confs_from_pkl(PKL_FILE, NOAH_DIR, START, END)
    noah_config_example = os.path.join(NOAH_DIR,"noah-owp-modular-init-cat-1496145.namelist.input")
    assert os.path.exists(noah_config_example)

def test_cfe_v22():
    os.system(f'mkdir -p {CFE_DIR}')
    gen_petAORcfe(GEOPACKAGE_PATH_v22,DATA_DIR,["CFE"])
    cfe_example = os.path.join(CFE_DIR,"CFE_cat-1496145.ini")
    assert os.path.exists(cfe_example)

def test_pet_v22():
    os.system(f'mkdir -p {PET_DIR}')
    gen_petAORcfe(GEOPACKAGE_PATH_v22,DATA_DIR,["PET"])
    pet_example = os.path.join(PET_DIR,"PET_cat-1496145.ini")
    assert os.path.exists(pet_example)    

def test_routing_v22():
    max_loop_size = (END - START + dt.timedelta(hours=1)).total_seconds() / (3600)
    generate_troute_conf(DATA_DIR,START,max_loop_size,GEOPACKAGE_PATH_v22) 
    yml_example = os.path.join(DATA_DIR,'troute.yaml')
    assert os.path.exists(yml_example)    



