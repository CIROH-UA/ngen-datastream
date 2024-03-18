import argparse, json, os
from datetime import datetime, timedelta
from pathlib import Path
import pytz as tz
import psutil
import subprocess

def generate_config(args):
    if args.host_type is None:
        host_type = args.host_type
    try:        
        host_type=str(subprocess.check_output("ec2-metadata --instance-type", shell=True))  
        host_type = host_type.split(": ")[1][:-3]
    except: 
        host_type="Not Specified"

    config = {
        "globals": {
            "domain_name"  : args.domain_name,
            "start_date"   : args.start_date,
            "end_date"     : args.end_date,
            "data_dir"     : args.data_dir,
            "gpkg"         : args.gpkg,
            "gpkg_attr"    : args.gpkg_attr,
            "resource_dir" : args.resource_dir,
            "nwmurl_file"  : args.nwmurl_file,
            "nprocs"       : args.nprocs
        },
        "subset": {
            "id_type"      : args.subset_id_type,
            "id"           : args.subset_id,
            "version"      : args.hydrofabric_version
        },
        "host":{
            "host_cores"   : os.cpu_count(),
            "host_RAM"     : psutil.virtual_memory()[0],    
            "host_type"    : host_type
        }
    }
    return config

def write_json(conf, out_dir, name):
    conf_path = Path(out_dir,name)
    with open(conf_path,'w') as fp:
        json.dump(conf, fp, indent=2)
    return conf_path

def create_conf_fp(start,end,ii_retro,nprocs):
    if ii_retro:
        filename = "retro_filenamelist.txt"
    else:
        filename = "filenamelist.txt"
    
    fp_conf = {
        "forcing" : {
            "start_date"   : start,
            "end_date"     : end,
            "nwm_file"     : f"/mounted_dir/datastream-resources/{filename}",
            "weight_file"  : "/mounted_dir/datastream-resources/weights.json",
        },
        "storage" : {
            "storage_type"     : "local",
            "output_bucket"    : "",
            "output_path"      : "/mounted_dir/ngen-run",
            "output_file_type" : "csv",
        },
        "run" : {
            "verbose"        : True,
            "collect_stats"  : True,
            "proc_process"   : os.cpu_count(),
            "write_process"  : os.cpu_count()
        }
    }

    return fp_conf

def create_conf_nwm_daily(start,end):

    num_hrs = 24
    nwm_conf = {
        "forcing_type" : "operational_archive",
        "start_date"   : start,
        "end_date"     : end,
        "runinput"     : 2,
        "varinput"     : 5,
        "geoinput"     : 1,
        "meminput"     : 0,
        "urlbaseinput" : 7,
        "fcst_cycle"   : [0],
        "lead_time"    : [x+1 for x in range(num_hrs)]
    }
    return nwm_conf    


def create_confs(conf):
        
    if conf['globals']['start_date'] == "DAILY":
        if conf['globals']['end_date'] != "":
            # allows for a "daily" run that is not the current date
            start_date = datetime.strptime(conf['globals']['end_date'],'%Y%m%d%H%M')
        else:
            start_date = datetime.now(tz.timezone('US/Eastern'))
        today = start_date.replace(hour=1, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(hours=23)

        if conf['globals'].get('data_dir',"") == "":
            conf['globals']['data_dir'] = today.strftime('%Y%m%d')      

        start = today.strftime('%Y%m%d%H%M')
        end = tomorrow.strftime('%Y%m%d%H%M')
        start_realization =  today.strftime('%Y-%m-%d %H:%M:%S')
        end_realization =  tomorrow.strftime('%Y-%m-%d %H:%M:%S')
        nwm_conf = create_conf_nwm_daily(start, end)

    else: 
        start = conf['globals']['start_date']
        end   = conf['globals']['end_date']
        start_realization =  datetime.strptime(start,'%Y%m%d%H%M').strftime('%Y-%m-%d %H:%M:%S')
        end_realization   =  datetime.strptime(end,'%Y%m%d%H%M').strftime('%Y-%m-%d %H:%M:%S')
        with open(conf['globals']['nwmurl_file'],'r') as fp:
            nwm_conf = json.load(fp)
            nwm_conf['start_date'] = start
            nwm_conf['end_date']   = end

    ii_retro = nwm_conf['forcing_type'] == 'retrospective'
    fp_conf = create_conf_fp(start, end, ii_retro,conf['globals']['nprocs'])  
    conf['nwmurl'] = nwm_conf 
    conf['forcingprocessor'] = nwm_conf      

    data_dir = Path(conf['globals']['data_dir'])
    ngen_config_dir = Path(data_dir,'ngen-run','config')
    datastream_config_dir = Path(data_dir,'datastream-configs')        

    write_json(nwm_conf,datastream_config_dir,'conf_nwmurl.json')
    write_json(fp_conf,datastream_config_dir,'conf_fp.json')
    write_json(conf,datastream_config_dir,'conf_datastream.json')

    print(f'\ndatastream configs have been generated and placed here\n{datastream_config_dir}\n')    
    
    realization_file = None
    for path, _, files in os.walk(ngen_config_dir):
        for jfile in files:
            jfile_path = os.path.join(path,jfile)
            if jfile_path.find('realization') >= 0: 
                realization_file = jfile_path

    if not realization_file: raise Exception(f"Cannot find realization file in {ngen_config_dir}")

    with open(realization_file,'r') as fp:
        data = json.load(fp)
    os.remove(realization_file)

    data['time']['start_time'] = start_realization
    data['time']['end_time']   = end_realization
    write_json(data,ngen_config_dir,'realization.json')    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--conf", type=str, help="A json containing user inputs to run ngen-datastream")
    parser.add_argument("--start-date", help="Set the start date")
    parser.add_argument("--end-date", help="Set the end date")
    parser.add_argument("--data-dir", help="Set the data directory")
    parser.add_argument("--gpkg",help="Path to geopackage file")    
    parser.add_argument("--gpkg_attr",help="Path to geopackage attributes file")
    parser.add_argument("--resource-dir", help="Set the resource directory")
    parser.add_argument("--subset-id-type", help="Set the subset ID type")
    parser.add_argument("--subset-id", help="Set the subset ID")
    parser.add_argument("--hydrofabric-version", help="Set the Hydrofabric version")
    parser.add_argument("--nwmurl_file", help="Provide an optional nwmurl file")
    parser.add_argument("--nprocs", type=int,help="Maximum number of processes to use")
    parser.add_argument("--host_type", type=str,help="Type of host",default=None)
    parser.add_argument("--domain_name", type=str,help="Name of spatial domain",default="Not Specified")

    args = parser.parse_args()

    if not args.conf:        
        conf = generate_config(args)
    else:
        conf = args.conf

    create_confs(conf)
