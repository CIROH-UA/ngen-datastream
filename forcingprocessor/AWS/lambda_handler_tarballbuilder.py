import boto3
import tarfile
import os
import datetime

client_s3  = boto3.client('s3')

def lambda_handler(event, context):

    forcings_bucket  = event['bucket']
    forcing_prefix   = event['prefix']
    forcings_key     = event['tar_key']
    forcing_filename = 'forcings.tar.gz'
    forcing_tar_path = f'/tmp/{forcing_filename}'
    print(f'{forcings_bucket} {forcings_key} {forcing_tar_path}')
    client_s3.download_file(forcings_bucket, forcings_key, forcing_tar_path)

    AWI_canonical_bucket   = "ngenforcingdev"
    AWI_canonical_key      = "AWI_03W_001.tar.gz"
    AWI_canonical_tar_path = f'/tmp/{AWI_canonical_key}'
    client_s3.download_file(AWI_canonical_bucket, AWI_canonical_key, AWI_canonical_tar_path)

    date = datetime.datetime.now()
    date = date.strftime('%Y%m%d')
    new_tar_name = f'dailyrun_{date}.tar.gz'
    new_tar = f'/tmp/{new_tar_name}'  
    new_tar_key = forcing_prefix + '/' + new_tar_name

    os.system(f'touch {new_tar}')
    
    with tarfile.open(new_tar,'w') as nw_tar:

        with tarfile.open(AWI_canonical_tar_path,'r:gz') as conf_tar:
            confs = [
                tarinfo for tarinfo in conf_tar.getmembers()
                if tarinfo.name.startswith("AWI_03W_001/config")
            ]

            with tarfile.open(forcing_tar_path,'r:gz') as forcings_tar:
                forcings = forcings_tar.getmembers()
                all_files = confs + forcings

                for jfile in all_files:
                    name = jfile.name
                    if name.find('.csv') >= 0:
                        obj = forcings_tar.extractfile(name)
                        jfile.name = 'forcings/' + jfile.name
                        nw_tar.addfile(jfile,obj)
                    else:
                        nw_tar.addfile(jfile,conf_tar.extractfile(name))

    client_s3.upload_file(new_tar, forcings_bucket, new_tar_key)   

    output = {"complete_tarball_key":new_tar_key,"bucket":forcings_bucket}
    return output   