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
    
    data_dir = '/tmp/data'
    os.mkdir(data_dir)
    os.system(f'tar -xzvf {ngen_input_tar_path} /tmp/data/')
    
    # This assumes ngen-cal has been place adjacent to this handler
    os.system('pip install -e ./ngen-cal')

    pkg_dir = Path(os.path.dirname(__file__), "ngen-cal/python")
    sys.path.append(str(pkg_dir))
    from conf_validation import validate

    forcing_files     = []
    input_files = os.listdir(data_dir)
    for jfile in input_files:
        jfile_path = os.path.join(data_dir,jfile)
        if jfile.find('catchment') >= 0: catchment_file = jfile_path
        if jfile.find('nexus') >= 0: nexus_file = jfile_path
        if jfile.find('realization') >= 0: realization_file = jfile_path
        if jfile.find('forcing') >= 0: forcing_files.append(jfile_path) 

    validate(catchment_file,"",nexus_file,"",realization_file)

    serialized_realization = NgenRealization.parse_file(realization_file)

    







    output = {}

    return output   