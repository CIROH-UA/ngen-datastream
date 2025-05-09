import pytest, os
from python_tools.run_validator import validate_data_dir

SCRIPT_DIR   = os.path.dirname(os.path.realpath(__file__))
DATA_DIR     = os.path.join(SCRIPT_DIR,'data')
DATA_PACKAGE = "https://datastream-resources.s3.us-east-1.amazonaws.com/validator.tar.gz"
ORIGINAL_TAR = "validator_test_original.tar.gz"
ORIGINAL_TAR_PATH = os.path.join(DATA_DIR,ORIGINAL_TAR)
TEST_DIR = os.path.join(DATA_DIR,"test_dir")
TEST_DATA_DIR = os.path.join(TEST_DIR,"ngen-run")
os.system(f"curl -o {ORIGINAL_TAR_PATH} -L -O {DATA_PACKAGE}")

@pytest.fixture(autouse=True)
def ready_test_folder():   
    if os.path.exists(TEST_DIR):
        os.system(f"rm -rf {TEST_DIR}")
    os.system(f'mkdir {TEST_DIR}')
    os.system(f"tar xfz {ORIGINAL_TAR_PATH} -C {TEST_DIR}")

def test_missing_geopackage():
    del_file = str(TEST_DATA_DIR) + '/config/*.gpkg'
    os.system(f"rm {del_file}")
    try:
        validate_data_dir(TEST_DATA_DIR)
        assert False 
    except Exception as inst:
        assert inst.__str__() == "Did not find geopackage file in ngen-run/config!!!"

def test_duplicate_geopackage():
    geo_file = str(TEST_DATA_DIR) + '/config/*.gpkg'
    geo_file2 = str(TEST_DATA_DIR) + '/config/extra.gpkg'
    os.system(f"cp {geo_file} {geo_file2}")
    try:
        validate_data_dir(TEST_DATA_DIR)
        assert False 
    except Exception as inst:
        assert inst.__str__() == "This run directory contains more than a single geopackage file, remove all but one."        

def test_missing_realization():
    del_file = str(TEST_DATA_DIR) + '/config/*realization*.json'
    os.system(f"rm {del_file}")
    try:
        validate_data_dir(TEST_DATA_DIR)
        assert False 
    except Exception as inst:
        assert inst.__str__() == "Did not find realization file in ngen-run/config!!!"

def test_duplicate_realization():
    real_file = str(TEST_DATA_DIR) + '/config/*realization*.json'
    real_file2 = str(TEST_DATA_DIR) + '/config/extra_realization.json'
    os.system(f"cp {real_file} {real_file2}")
    try:
        validate_data_dir(TEST_DATA_DIR)
        assert False 
    except Exception as inst:
        assert inst.__str__() == "This run directory contains more than a single realization file, remove all but one."        


def test_missing_bmi_config():
    del_file = str(TEST_DATA_DIR) + '/config/cat_config/CFE/CFE_cat-1496145.ini'
    os.system(f"rm {del_file}")
    try:
        validate_data_dir(TEST_DATA_DIR)
        assert False 
    except Exception as inst:
        assert inst.__str__() == "cat-1496145 -> File config/cat_config/CFE/CFE_cat-1496146.ini does not match pattern specified config/cat_config/CFE/CFE_{{id}}.ini"                

def test_missing_forcings():
    del_file = str(TEST_DATA_DIR) + '/forcings/*.nc'
    os.system(f"rm {del_file}")
    try:
        validate_data_dir(TEST_DATA_DIR)
        assert False 
    except Exception as inst:
        assert inst.__str__() == f"Forcings file not found!"  

def test_forcings_time_axis():
    del_file = str(TEST_DATA_DIR) + '/forcings/*.nc'
    os.system(f"rm {del_file}")
    os.system(f"curl -L -O https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2/ngen.20250506/forcing_short_range/02/ngen.t02z.short_range.forcing.f001_f018.VPU_09.nc")
    new_forcings = os.path.join(TEST_DATA_DIR,"forcings/1_forcings.nc")
    os.system(f"mv ngen.t02z.short_range.forcing.f001_f018.VPU_09.nc {new_forcings}")
    try:
        validate_data_dir(TEST_DATA_DIR)
        assert False 
    except Exception as inst:
        assert inst.__str__() == f"Realization start time 2025-02-28 01:00:00+00:00 does not match forcing start time 2025-05-06 03:00:00+00:00"          

def test_missing_troute_config():
    del_file = str(TEST_DATA_DIR) + '/config/ngen.yaml'
    os.system(f"rm {del_file}")
    try:
        validate_data_dir(TEST_DATA_DIR)
        assert False 
    except Exception as inst:
        assert inst.__str__() == "t-route specified in config, but not found"         