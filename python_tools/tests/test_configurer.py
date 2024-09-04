import os, pytest, json
from datetime import datetime
from python_tools.configure_datastream import config_class2dict, create_confs

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
                 data_path="",
                 gpkg="",
                 resource_path="",
                 forcings="",
                 forcing_source="",
                 subset_id_type="",
                 subset_id="",
                 hydrofabric_version="",
                 nprocs=None,
                 host_os="",
                 domain_name="Not Specified",
                 forcing_split_vpu=False,
                 realization_file=""):
        self.docker_mount = docker_mount
        self.start_date = start_date
        self.end_date = end_date
        self.data_path = data_path
        self.gpkg = gpkg
        self.resource_path = resource_path
        self.forcings = forcings
        self.forcing_source = forcing_source
        self.subset_id_type = subset_id_type
        self.subset_id = subset_id
        self.hydrofabric_version = hydrofabric_version
        self.nprocs = nprocs if nprocs is not None else os.cpu_count()
        self.host_os = host_os
        self.domain_name = domain_name
        self.forcing_split_vpu = forcing_split_vpu
        self.realization_file = realization_file

inputs = Inputs(
    docker_mount = "/mounted_dir",
    start_date = "202406100000",
    end_date = "202406102300",
    data_path = str(DATA_DIR),
    gpkg = str(os.path.join(DATA_DIR,"palisade.gpkg")),
    resource_path = "",
    forcings = "",
    forcing_source = "NWM_RETRO_V3",
    subset_id_type = "",
    subset_id = "",
    hydrofabric_version = "",
    nprocs = 2,
    host_os = "Linux",
    domain_name = "",
    forcing_split_vpu = False,
    realization_file = str(REALIZATION_ORIG)
)

@pytest.fixture
def clean_dir():
    if os.path.exists(DATA_DIR):
        os.system(f'rm -rf {str(DATA_DIR)}')
    os.system(f'mkdir {str(DATA_DIR)}')

def test_conf_basic(clean_dir):
    create_confs(inputs)
    assert os.path.exists(CONF_NWM)
    assert os.path.exists(CONF_FP)
    assert os.path.exists(CONF_DATASTREAM)
    assert os.path.exists(REALIZATION_META_USER)   
    assert os.path.exists(REALIZATION_META_DS)   
    assert os.path.exists(REALIZATION_RUN) 

def test_conf_daily(clean_dir):
    inputs.start_date = "DAILY"
    inputs.end_date   = ""
    create_confs(inputs)
    assert os.path.exists(CONF_NWM)
    assert os.path.exists(CONF_FP)
    assert os.path.exists(CONF_DATASTREAM)
    assert os.path.exists(REALIZATION_META_USER)   
    assert os.path.exists(REALIZATION_META_DS)   
    assert os.path.exists(REALIZATION_RUN)  

    with open(REALIZATION_RUN,'r') as fp:
        data = json.load(fp) 

    start = datetime.strptime(data['time']['start_time'],"%Y-%m-%d %H:%M:%S")
    assert start.day == datetime.today().day



