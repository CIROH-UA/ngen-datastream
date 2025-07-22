import os, pytest, json
from datetime import datetime, timezone, timedelta
from python_tools.configure_datastream import create_confs

SCRIPT_DIR        = os.path.dirname(os.path.realpath(__file__))
DATA_DIR          = os.path.join(SCRIPT_DIR,'data')
METADATA_DIR      = os.path.join(DATA_DIR,"datastream-metadata")
DATASTREAM_DIR    = os.path.dirname(os.path.dirname(SCRIPT_DIR))
REALIZATION_FILE  = "realization_sloth_nom_cfe_pet.json"
REALIZATION_ORIG  = os.path.join(DATASTREAM_DIR,"configs/ngen/",REALIZATION_FILE)
NGEN_RUN_CONF_DIR = os.path.join(DATA_DIR,"ngen-run/config")
REALIZATION_RUN   = os.path.join(NGEN_RUN_CONF_DIR,"realization.json")
REALIZATION_META_USER  = os.path.join(METADATA_DIR,"realization_user.json")
REALIZATION_META_DS    = os.path.join(METADATA_DIR,"realization_datastream.json")
CONF_NWM          = os.path.join(METADATA_DIR,'conf_nwmurl.json')
CONF_FP           = os.path.join(METADATA_DIR,'conf_fp.json')
CONF_DATASTREAM   = os.path.join(METADATA_DIR,'conf_datastream.json')

class Inputs:
    def __init__(self,
                 docker_mount="",
                 start_date=None,
                 end_date="",
                 data_dir="",
                 geopackage="",
                 geopackage_provided="",
                 resource_path="",
                 forcings="",
                 forcing_source="",
                 subset_id_type="",
                 subset_id="",
                 hydrofabric_version="",
                 nprocs=None,
                 host_os="",
                 united_conus="",
                 domain_name="Not Specified",
                 forcing_split_vpu="",
                 realization="",
                 realization_provided="",
                 s3_bucket="",
                 s3_prefix="",
                 ngen_bmi_confs=""):
        self.docker_mount = docker_mount
        self.start_date = start_date
        self.end_date = end_date
        self.data_dir = data_dir
        self.geopackage = geopackage
        self.geopackage_provided = geopackage_provided
        self.resource_path = resource_path
        self.forcings = forcings
        self.forcing_source = forcing_source
        self.subset_id_type = subset_id_type
        self.subset_id = subset_id
        self.hydrofabric_version = hydrofabric_version
        self.nprocs = nprocs if nprocs is not None else os.cpu_count()
        self.host_os = host_os
        self.united_conus = united_conus
        self.domain_name = domain_name
        self.forcing_split_vpu = forcing_split_vpu
        self.realization = realization
        self.realization_provided = realization_provided
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.ngen_bmi_confs = ngen_bmi_confs

inputs = Inputs(
    docker_mount = "/mounted_dir",
    start_date = "202406100000",
    end_date = "202406102300",
    data_dir = str(DATA_DIR),
    geopackage = str(os.path.join(DATA_DIR,"palisade.gpkg")),
    geopackage_provided = str(os.path.join(DATA_DIR,"palisade.gpkg")),
    resource_path = "",
    forcings = "",
    forcing_source = "NWM_RETRO_V3",
    subset_id_type = "",
    subset_id = "",
    hydrofabric_version = "",
    nprocs = 2,
    host_os = "Linux",
    united_conus = False,
    domain_name = "",
    forcing_split_vpu = "",
    realization = str(REALIZATION_ORIG),
    realization_provided = str(REALIZATION_ORIG),
    s3_bucket="",
    s3_prefix="",
    ngen_bmi_confs=""
)

@pytest.fixture
def clean_dir(autouse=True):
    if os.path.exists(DATA_DIR):
        os.system(f'rm -rf {str(DATA_DIR)}')
    os.system(f'mkdir {str(DATA_DIR)}')

def check_paths():
    assert os.path.exists(CONF_NWM)
    assert os.path.exists(CONF_FP)
    assert os.path.exists(CONF_DATASTREAM)
    assert os.path.exists(REALIZATION_META_USER)   
    assert os.path.exists(REALIZATION_META_DS)   
    assert os.path.exists(REALIZATION_RUN) 

def test_conf_basic():
    create_confs(inputs)
    check_paths()

    with open(CONF_FP,'r') as fp:
        data = json.load(fp)   
    assert data['storage']['output_path'] == "/mounted_dir/ngen-run"  
    assert data['forcing']['gpkg_file'][0] == "/mounted_dir/datastream-resources/config/palisade.gpkg"

def test_conf_daily():
    inputs.start_date = "DAILY"
    inputs.end_date   = ""
    inputs.forcing_source = "NWM_V3"
    create_confs(inputs)
    check_paths()

    with open(REALIZATION_RUN,'r') as fp:
        data = json.load(fp) 
    start = datetime.strptime(data['time']['start_time'],"%Y-%m-%d %H:%M:%S")
    assert start.day == datetime.now(timezone.utc).day

    with open(CONF_NWM,'r') as fp:
        data = json.load(fp)   
    assert data['urlbaseinput'] == 7

def test_conf_daily_pick():
    inputs.start_date = "DAILY"
    inputs.end_date   = "202006200000"
    inputs.forcing_source = "NWM_RETRO_V3"
    create_confs(inputs)
    check_paths()

    with open(REALIZATION_RUN,'r') as fp:
        data = json.load(fp) 
    start = datetime.strptime(data['time']['start_time'],"%Y-%m-%d %H:%M:%S")
    assert start.day == datetime.strptime(inputs.end_date,"%Y%m%d%H%M%S").day  

    with open(CONF_NWM,'r') as fp:
        data = json.load(fp)
    assert data['urlbaseinput'] == 4

def test_conf_daily_short_range_init00():
    inputs.start_date = "DAILY"
    inputs.end_date   = ""
    inputs.forcing_source = "NWM_V3_SHORT_RANGE_00"
    create_confs(inputs)
    check_paths()

    with open(REALIZATION_RUN,'r') as fp:
        data = json.load(fp) 
    start = datetime.strptime(data['time']['start_time'],"%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(data['time']['end_time'],"%Y-%m-%d %H:%M:%S")
    assert start.day == datetime.now(timezone.utc).day
    assert end.day == datetime.now(timezone.utc).day
    assert end.hour == 18

    with open(CONF_NWM,'r') as fp:
        data = json.load(fp)   
    assert data['urlbaseinput'] == 7 
    assert data['runinput']     == 1   

def test_conf_daily_short_range_init15():
    inputs.start_date = "DAILY"
    inputs.end_date   = ""
    inputs.forcing_source = "NWM_V3_SHORT_RANGE_15"
    create_confs(inputs)
    check_paths()

    with open(REALIZATION_RUN,'r') as fp:
        data = json.load(fp) 
    start = datetime.strptime(data['time']['start_time'],"%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(data['time']['end_time'],"%Y-%m-%d %H:%M:%S")
    assert (start.day == (datetime.now(timezone.utc)).day) or (start.day == (datetime.now(timezone.utc) - timedelta(days=1)).day)
    assert start.hour == 16
    assert (end.day == (datetime.now(timezone.utc) + timedelta(days=1)).day) or (end.day == (datetime.now(timezone.utc)).day)
    assert end.hour == 9

    with open(CONF_NWM,'r') as fp:
        data = json.load(fp)   
    assert data['urlbaseinput'] == 7 
    assert data['runinput']     == 1      

def test_conf_daily_short_range_init23():
    inputs.start_date = "DAILY"
    inputs.end_date   = ""
    inputs.forcing_source = "NWM_V3_SHORT_RANGE_23"
    create_confs(inputs)
    check_paths()

    with open(REALIZATION_RUN,'r') as fp:
        data = json.load(fp) 
    start = datetime.strptime(data['time']['start_time'],"%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(data['time']['end_time'],"%Y-%m-%d %H:%M:%S")
    assert start.day == (datetime.now(timezone.utc)).day or start.day == (datetime.now(timezone.utc) - timedelta(days=1)).day
    assert start.hour == 0
    assert end.day == (datetime.now(timezone.utc) + timedelta(days=1)).day or end.day == (datetime.now(timezone.utc)).day
    assert end.hour == 17

    with open(CONF_NWM,'r') as fp:
        data = json.load(fp)   
    assert data['urlbaseinput'] == 7 
    assert data['runinput']     == 1      

def test_conf_daily_medium_range_init00_member0():
    inputs.start_date = "DAILY"
    inputs.end_date   = ""
    inputs.forcing_source = "NWM_V3_MEDIUM_RANGE_00_0"
    create_confs(inputs)
    check_paths()

    with open(REALIZATION_RUN,'r') as fp:
        data = json.load(fp) 
    start = datetime.strptime(data['time']['start_time'],"%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(data['time']['end_time'],"%Y-%m-%d %H:%M:%S")
    assert start.day == datetime.now(timezone.utc).day
    assert start.hour == 1
    assert end.day == (datetime.now(timezone.utc) + timedelta(days=10)).day
    assert end.hour == 0

    with open(CONF_NWM,'r') as fp:
        data = json.load(fp)   
    assert data['urlbaseinput'] == 7 
    assert data['runinput']     == 2   
    assert data['meminput']     == 0

def test_conf_daily_medium_range_init12_member3():
    inputs.start_date = "DAILY"
    inputs.end_date   = ""
    inputs.forcing_source = "NWM_V3_MEDIUM_RANGE_12_3"
    create_confs(inputs)
    check_paths()

    with open(REALIZATION_RUN,'r') as fp:
        data = json.load(fp) 
    start = datetime.strptime(data['time']['start_time'],"%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(data['time']['end_time'],"%Y-%m-%d %H:%M:%S")
    assert start.day == (datetime.now(timezone.utc)).day or start.day == (datetime.now(timezone.utc) - timedelta(days=1)).day
    assert start.hour == 13
    assert end.day == (datetime.now(timezone.utc) + timedelta(days=10)).day or end.day == (datetime.now(timezone.utc) + timedelta(days=9)).day
    assert end.hour == 12

    with open(CONF_NWM,'r') as fp:
        data = json.load(fp)   
    assert data['urlbaseinput'] == 7 
    assert data['runinput']     == 2   
    assert data['meminput']     == 3  

def test_conf_daily_noamds():
    inputs.start_date = "DAILY"
    inputs.end_date   = ""
    inputs.forcing_source = "NOMADS_MEDIUM_RANGE_00_0"
    create_confs(inputs)
    check_paths()

    with open(REALIZATION_RUN,'r') as fp:
        data = json.load(fp) 
    start = datetime.strptime(data['time']['start_time'],"%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(data['time']['end_time'],"%Y-%m-%d %H:%M:%S")
    assert start.day == datetime.now(timezone.utc).day
    assert end.day == (datetime.now(timezone.utc)+timedelta(hours=240-1)).day
    assert end.hour == 0

    with open(CONF_NWM,'r') as fp:
        data = json.load(fp)   
    assert data['urlbaseinput'] == 1 
    assert data['runinput']     == 2      

def test_conf_daily_noamds_postprocessed():
    inputs.start_date = "DAILY"
    inputs.end_date   = ""
    inputs.forcing_source = "NOMADS_POSTPROCESSED_MEDIUM_RANGE_00_0"
    create_confs(inputs)
    check_paths()

    with open(REALIZATION_RUN,'r') as fp:
        data = json.load(fp) 
    start = datetime.strptime(data['time']['start_time'],"%Y-%m-%d %H:%M:%S")
    assert start.day == datetime.now(timezone.utc).day

    with open(CONF_NWM,'r') as fp:
        data = json.load(fp)   
    assert data['urlbaseinput'] == 2
    assert data['runinput']     == 2  

def test_conf_daily_assim_split_vpu_s3out():
    inputs.start_date = "DAILY"
    inputs.end_date   = ""
    inputs.forcing_source = "NWM_V3_ANALYSIS_ASSIM"
    inputs.forcing_split_vpu = "01,02,03W,16"
    inputs.s3_bucket = "ciroh-community-ngen-datastream"
    inputs.s3_prefix = "pytest"
    create_confs(inputs)
    check_paths()

    with open(REALIZATION_RUN,'r') as fp:
        data = json.load(fp) 
    start = datetime.strptime(data['time']['start_time'],"%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(data['time']['end_time'],"%Y-%m-%d %H:%M:%S")        
    assert start.hour == 22
    assert start.day == (datetime.now(timezone.utc)).day or start.day == (datetime.now(timezone.utc) - timedelta(days=1)).day
    assert end.day == (datetime.now(timezone.utc) + timedelta(days=1)).day or end.day == (datetime.now(timezone.utc)).day
    assert end.hour == 1

    with open(CONF_NWM,'r') as fp:
        data = json.load(fp)   
    assert data['urlbaseinput'] == 7 
    assert data['runinput']     == 5 
    assert len(data['lead_time'] ) == 3

    with open(CONF_FP,'r') as fp:
        data = json.load(fp)   
    assert len(data['forcing']['gpkg_file']) == 4
    assert data['storage']['output_path'].startswith("s3://ciroh-community-ngen-datastream/pytest")    

     
def test_conf_daily_assim_extend_split_vpu_s3out():
    inputs.start_date = "DAILY"
    inputs.end_date   = ""
    inputs.forcing_source = "NWM_V3_ANALYSIS_ASSIM_EXTEND_16"
    inputs.forcing_split_vpu = "01,02,03W,16"
    inputs.s3_bucket = "ciroh-community-ngen-datastream"
    inputs.s3_prefix = "pytest"
    create_confs(inputs)
    check_paths()

    with open(REALIZATION_RUN,'r') as fp:
        data = json.load(fp) 
    start = datetime.strptime(data['time']['start_time'],"%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(data['time']['end_time'],"%Y-%m-%d %H:%M:%S")
    assert start.hour == 13
    assert start.day == (datetime.now(timezone.utc)).day or start.day == (datetime.now(timezone.utc) - timedelta(days=1)).day or start.day == (datetime.now(timezone.utc) - timedelta(days=2)).day
    assert end.day == (datetime.now(timezone.utc) + timedelta(days=1)).day or end.day == (datetime.now(timezone.utc)).day or end.day == (datetime.now(timezone.utc) - timedelta(days=1)).day
    assert end.hour == 16

    with open(CONF_NWM,'r') as fp:
        data = json.load(fp)   
    assert data['urlbaseinput']    == 7 
    assert data['runinput']        == 6
    assert data['fcst_cycle'][0]   == 16
    assert len(data['lead_time'] ) == 28

    with open(CONF_FP,'r') as fp:
        data = json.load(fp)   
    assert len(data['forcing']['gpkg_file']) == 4
    assert data['storage']['output_path'].startswith("s3://ciroh-community-ngen-datastream/pytest")

def test_conf_forcings_provided():
    inputs.start_date = "202410300100"
    inputs.end_date   = "202410300400"
    inputs.forcing_source = ""
    inputs.forcings = "test_file.nc"
    inputs.forcing_split_vpu = "01,02,03W,16"
    inputs.s3_bucket = ""
    inputs.s3_prefix = ""  
    create_confs(inputs)
    check_paths()    

    with open(REALIZATION_RUN,'r') as fp:
        data = json.load(fp) 
    start = datetime.strptime(data['time']['start_time'],"%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(data['time']['end_time'],"%Y-%m-%d %H:%M:%S")
    assert start.hour == 1
    assert start.day == 30
    assert end.hour == 4   
    assert end.day == 30
    




