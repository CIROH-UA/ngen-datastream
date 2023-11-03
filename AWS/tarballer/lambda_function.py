import boto3
import tarfile
import os
import datetime

client_s3  = boto3.client('s3')

def lambda_handler(event, context):

    tar1_bucket  = event['bucket']
    tar1_prefix  = event['prefix']
    tar1_key     = event['obj_key']

    tar2_bucket  = event['config_bucket']
    run_type     = event['run_type']

    tar1_filename = tar1_key.split('/')[-1]
    tar1_tar_path = f'/tmp/{tar1_filename}'
    client_s3.download_file(tar1_bucket, tar1_prefix + tar1_key, tar1_tar_path)

    tar2_key      = f"{run_type}.tar.gz"
    tar2_tar_path = f'/tmp/{tar2_key}'
    client_s3.download_file(tar2_bucket, tar2_key, tar2_tar_path)

    date = datetime.datetime.now()
    date = date.strftime('%Y%m%d')
    new_tar_name = f'{run_type}_{date}.tar.gz'
    new_tar      = f'/tmp/{new_tar_name}'  
    new_tar_key  = tar1_prefix + '/' + new_tar_name

    os.system(f'touch {new_tar}')
    
    with tarfile.open(new_tar,'w:gz') as nw_tar:

        with tarfile.open(tar2_tar_path,'r:gz') as tar2:
            confs = [
                tarinfo for tarinfo in tar2.getmembers()
            ]
            
            with tarfile.open(tar1_tar_path,'r:gz') as tar1_tar:
                forcings = tar1_tar.getmembers()
                all_files = confs + forcings

                for jfile in all_files:
                    name = jfile.name
                    if name.find('.csv') >= 0:
                        obj = tar1_tar.extractfile(name)
                        nw_tar.addfile(jfile,obj)
                    else:
                        nw_tar.addfile(jfile,tar2.extractfile(name))

    client_s3.upload_file(new_tar, tar1_bucket, new_tar_key)    

    event["complete_tarball_key"] = new_tar_key
    return event   