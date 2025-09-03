# test_nrds_fp.py
#
# Author: Jordan Laser <jlaser@lynker.com>
# 
# 
# Test the NRDS forcing processing by inputing all 21 VPU's weight files, 
# processing a single nwm forcing file, and the writing to a test location in the producting bucket.

import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from forcingprocessor.processor import prep_ngen_data
from forcingprocessor.nwm_filenames_generator import generate_nwmfiles
import pytest
from forcingprocessor.utils import vpus
import boto3
from botocore.exceptions import ClientError
import re

HF_VERSION="v2.2"
TODAY = datetime.now(timezone.utc)
TODAY_YYMMDD = TODAY.strftime('%Y%m%d')
hourminute  = '0000'
TODAY_YYMMDDHHMM = TODAY_YYMMDD + hourminute
YESTERDAY = TODAY - timedelta(hours=24)
YESTERDAY_YYMMDD = YESTERDAY.strftime('%Y%m%d')
YESTERDAY_YYMMDDHHMM = YESTERDAY_YYMMDD + hourminute
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

weight_files = [f"https://ciroh-community-ngen-datastream.s3.amazonaws.com/v2.2_resources/weights/nextgen_VPU_{x}_weights.json" for x in vpus]
local_weight_files = [str((data_dir/f"nextgen_VPU_{x}_weights.json").resolve()) for x in vpus]

# download weight files
for j, wf in enumerate(weight_files):
    local_file = local_weight_files[j]
    if not os.path.exists(local_file):
        os.system(f"wget {wf} -P {data_dir}")

conf = {
    "forcing"  : {
        "nwm_file"   : filenamelist,
        "gpkg_file"  : local_weight_files
    },

    "storage":{
        "output_path"       : "s3://ciroh-community-ngen-datastream/test/nrds_fp_test/",
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
        "start_date"   : YESTERDAY_YYMMDDHHMM,
        "end_date"     : YESTERDAY_YYMMDDHHMM,
        "runinput"     : 1,
        "varinput"     : 5,
        "geoinput"     : 1,
        "meminput"     : 0,
        "urlbaseinput" : 7,
        "fcst_cycle"   : [0],
        "lead_time"    : [1]
    }

s3 = boto3.client("s3")

@pytest.fixture
def clean_dir(autouse=True):
    if os.path.exists(forcings_dir):
        os.system(f'rm -rf {str(forcings_dir)}')

def s3_object_exists(url: str) -> bool:
    m = re.match(r"s3://([^/]+)/(.+)", url)
    if not m:
        raise ValueError(f"Invalid S3 URL: {url}")
    bucket, key = m.groups()

    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        else:
            raise

def test_nrds_fp():
    generate_nwmfiles(nwmurl_conf)  
    conf['run']['collect_stats'] = False 
    prep_ngen_data(conf)

    for vpu in vpus:
        url = f"s3://ciroh-community-ngen-datastream/test/nrds_fp_test/ngen.t00z.short_range.forcing.f001_f018.VPU_{vpu}.nc"
        print(f"Checking for {url}")
        assert s3_object_exists(url)

if __name__ == "__main__":
    test_nrds_fp()
    
