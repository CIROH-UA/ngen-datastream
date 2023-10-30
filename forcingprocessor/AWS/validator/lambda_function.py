import boto3
import os, sys
from pathlib import Path
from ngen.config.realization import NgenRealization

client_s3  = boto3.client('s3')

def lambda_handler(event, context):

    os.system('pip install -e ./ngen-cal')

    ngen_input_bucket   = event['bucket']
    ngen_input_key      = event['complete_tarball_key']
    ngen_input_filename = 'ngen_inputs.tar.gz'
    ngen_input_tar_path = f'/tmp/{ngen_input_filename}'
    client_s3.download_file(ngen_input_bucket, ngen_input_key, ngen_input_tar_path)
    
    # This assumes ngen-cal has been place adjacent to this handler
    os.system('pip install -e ./ngen-cal/python/ngen_conf')

    pkg_dir = Path(os.path.dirname(__file__), "ngen-cal/python")
    sys.path.append(str(pkg_dir))
    from conf_validation import validate_tar
    validate_tar(ngen_input_tar_path)

    output = {}

    return output   