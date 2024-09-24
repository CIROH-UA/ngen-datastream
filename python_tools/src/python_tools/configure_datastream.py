import argparse, json, os
from datetime import datetime, timedelta
from pathlib import Path
import pytz as tz
import platform
import psutil

def bytes2human(n):
    # http://code.activestate.com/recipes/578019
    # >>> bytes2human(10000)
    # '9.8K'
    # >>> bytes2human(100001221)
    # '95.4M'
    symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i + 1) * 10
    for s in reversed(symbols):
        if abs(n) >= prefix[s]:
            value = float(n) / prefix[s]
            return '%.1f%s' % (value, s)
    return "%sB" % n

def config_class2dict(args):
    config = {
        "globals": {
            "domain_name"   : args.domain_name,
            "start_date"    : args.start_date,
            "end_date"      : args.end_date,
            "data_path"     : args.data_path,
            "gpkg"          : args.gpkg,
            "resource_path" : args.resource_path,
            "forcings"      : args.forcings,
            "nprocs"        : args.nprocs,
            "forcing_split_vpu"    : args.forcing_split_vpu
        }, 
        "subset": {
            "id_type"      : args.subset_id_type,
            "id"           : args.subset_id,
            "version"      : args.hydrofabric_version
        },
        "host":{
            "host_cores"     : os.cpu_count(),
            "host_RAM"       : bytes2human(psutil.virtual_memory()[0]),    
            "host_OS"        : args.host_os,
            "host_platform"  : platform.machine()
        }
    }
    return config

def write_json(conf, out_dir, name):
    conf_path = Path(out_dir,name)
    if not os.path.exists(out_dir):
        os.system(f'mkdir -p {out_dir}')
    with open(conf_path,'w') as fp:
        json.dump(conf, fp, indent=2)
    return conf_path

def create_conf_fp(start,end,nprocs,docker_mount,forcing_split_vpu,retro_or_op,geo_base):
    if retro_or_op == "retrospective":
        filename = "retro_filenamelist.txt"
    else:
        filename = "filenamelist.txt"
    
    if forcing_split_vpu:
        weights = [
            "s3://ngen-datastream/resources/v20.1/VPU_01/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_02/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_03N/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_03S/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_03W/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_04/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_05/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_06/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_07/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_08/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_09/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_10L/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_10U/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_11/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_12/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_13/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_14/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_15/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_16/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_17/weights.json",
            "s3://ngen-datastream/resources/v20.1/VPU_18/weights.json"
        ]
        output_path  = f"s3://ngen-datastream/forcings/v20.1/{start}-{end}"
        output_file_type = ["tar"]
    else:
        weights = [f"{docker_mount}/datastream-resources/config/{geo_base}"]
        output_path = f"{docker_mount}/ngen-run"
        output_file_type = ["netcdf"]

    fp_conf = {
        "forcing" : {
            "nwm_file"     : f"{docker_mount}/datastream-metadata/{filename}",
            "gpkg_file"    : weights,
        },
        "storage" : {
            "output_path"      : output_path,
            "output_file_type" : output_file_type,
        },
        "run" : {
            "verbose"        : True,
            "collect_stats"  : True,
            "nprocs"         : min(os.cpu_count(),nprocs),
        }
    }

    return fp_conf

def create_conf_nwm(start, end, retro_or_op,urlbaseinput):

    if retro_or_op == "retrospective":
        nwm_conf = {
        "forcing_type" : "retrospective",
        "start_date"   : start,
        "end_date"     : end,
        "urlbaseinput" : urlbaseinput,
        "selected_object_type" : [1],
        "selected_var_types"   : [6],
        "write_to_file"        : True
        }   
    else:
        start_df = datetime.strptime(start,'%Y%m%d%H%M')
        end_df   = datetime.strptime(end,'%Y%m%d%H%M')
        diff_days = (end_df - start_df).days
        if diff_days == 0:
            num_hrs = int((end_df - start_df).seconds / 3600) + 1
        else:
            num_hrs = 24

        nwm_conf = {
            "forcing_type" : "operational_archive",
            "start_date"   : start,
            "end_date"     : end,
            "runinput"     : 2,
            "varinput"     : 5,
            "geoinput"     : 1,
            "meminput"     : 0,
            "urlbaseinput" : urlbaseinput,
            "fcst_cycle"   : [0],
            "lead_time"    : [x+1 for x in range(num_hrs)]
        }

    return nwm_conf  

def create_confs(args):
    conf = config_class2dict(args)
    realization = args.realization_file
    geo_base = args.gpkg.split('/')[-1]

    if "OPERATIONAL" in args.forcing_source:    
        retro_or_op = "operational"         
        if "V3" in args.forcing_source:
            urlbaseinput = 7
        if "NOMADS" in args.forcing_source:
            urlbaseinput = 1                   
    elif "RETRO" in args.forcing_source:   
        retro_or_op = "retrospective"          
        if "V2" in args.forcing_source:
            urlbaseinput = 1
        if "V3" in args.forcing_source:
            urlbaseinput = 4   
        
    if conf['globals']['start_date'] == "DAILY":
        if conf['globals']['end_date'] != "":
            # allows for a "daily" run that is not the current date
            start_date = datetime.strptime(conf['globals']['end_date'],'%Y%m%d%H%M')
        else:
            start_date = datetime.now(tz.timezone('US/Eastern'))
            retro_or_op="operational"
            urlbaseinput=7
        today = start_date.replace(hour=1, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(hours=23)

        if conf['globals'].get('data_path',"") == "":
            conf['globals']['data_path'] = today.strftime('%Y%m%d')      

        start = today.strftime('%Y%m%d%H%M')
        end = tomorrow.strftime('%Y%m%d%H%M')
        start_realization =  today.strftime('%Y-%m-%d %H:%M:%S')
        end_realization =  tomorrow.strftime('%Y-%m-%d %H:%M:%S')
        nwm_conf = create_conf_nwm(start, end, retro_or_op, urlbaseinput)
        fp_conf = create_conf_fp(start, end, conf['globals']['nprocs'],args.docker_mount,args.forcing_split_vpu,retro_or_op,geo_base) 
    else: 
        start = conf['globals']['start_date']
        end   = conf['globals']['end_date']
        start_realization_dt = datetime.strptime(start,'%Y%m%d%H%M')
        end_realization_dt = datetime.strptime(end,'%Y%m%d%H%M')
        start_realization =  start_realization_dt.strftime('%Y-%m-%d %H:%M:%S')
        end_realization   = end_realization_dt.strftime('%Y-%m-%d %H:%M:%S')
        if args.forcings.endswith(".nc") or args.forcings.endswith(".tar.gz"):
            nwm_conf = {}
            fp_conf = {}
            fp_conf['forcing'] = args.forcings
        elif os.path.exists(os.path.join(args.resource_path,"nwm-forcings")):
            nwm_conf = {}
            fp_conf  = create_conf_fp(start, end, conf['globals']['nprocs'], args.docker_mount, args.forcing_split_vpu,retro_or_op,geo_base) 
        else:
            nwm_conf = create_conf_nwm(start,end, retro_or_op,urlbaseinput)
            fp_conf  = create_conf_fp(start, end, conf['globals']['nprocs'], args.docker_mount, args.forcing_split_vpu,retro_or_op,geo_base) 

    conf['nwmurl'] = nwm_conf 
    conf['forcingprocessor'] = nwm_conf    

    if os.path.exists(args.docker_mount):
        data_path = Path(args.docker_mount)
    else:
        data_path = Path(conf['globals']['data_path'])

    ngen_config_dir = Path(data_path,'ngen-run','config')
    if not os.path.exists(ngen_config_dir): os.system(f'mkdir -p {ngen_config_dir}')

    datastream_meta_dir = Path(data_path,'datastream-metadata')    
    if not os.path.exists(datastream_meta_dir):os.system(f'mkdir -p {datastream_meta_dir}')

    write_json(nwm_conf,datastream_meta_dir,'conf_nwmurl.json')
    write_json(fp_conf,datastream_meta_dir,'conf_fp.json')
    write_json(conf,datastream_meta_dir,'conf_datastream.json')

    print(f'datastream metadata have been generated and placed here\n{datastream_meta_dir}')    
    
    with open(realization,'r') as fp:
        data = json.load(fp)
    write_json(data,datastream_meta_dir,'realization_user.json')

    data['time']['start_time'] = start_realization
    data['time']['end_time']   = end_realization    
    if args.forcings.endswith(".tar.gz"):
        data['global']['forcing']['file_pattern'] = ".*{{id}}.*.csv"
        data['global']['forcing']['path'] = "./forcings"
        data['global']['forcing']['provider'] = "CsvPerFeature"
    else:
        if "file_pattern" in data['global']['forcing']: del data['global']['forcing']['file_pattern']
        data['global']['forcing']['provider'] = "NetCDF"
        data['global']['forcing']['path'] = "./forcings/1_forcings.nc"
    write_json(data,ngen_config_dir,'realization.json')
    write_json(data,datastream_meta_dir,'realization_datastream.json')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--docker_mount", help="Path to DATA_PATH mount within docker container",default="")
    parser.add_argument("--start_date", help="Set the start date",default=None)
    parser.add_argument("--end_date", help="Set the end date",default="")
    parser.add_argument("--data_path", help="Set the data directory",default="")
    parser.add_argument("--gpkg",help="Path to geopackage file",default="")    
    parser.add_argument("--resource_path", help="Set the resource directory",default="")
    parser.add_argument("--forcings", help="Set the forcings file or directory",default="")
    parser.add_argument("--forcing_source", help="Option for source of forcings",default="")
    parser.add_argument("--subset_id_type", help="Set the subset ID type",default="")
    parser.add_argument("--subset_id", help="Set the subset ID",default="")
    parser.add_argument("--hydrofabric_version", help="Set the Hydrofabric version",default="")
    parser.add_argument("--nprocs", type=int,help="Maximum number of processes to use",default=os.cpu_count())
    parser.add_argument("--host_platform", type=str,help="Type of host",default="")
    parser.add_argument("--host_os", type=str,help="Operating system of host",default="")
    parser.add_argument("--domain_name", type=str,help="Name of spatial domain",default="Not Specified")
    parser.add_argument("--forcing_split_vpu", type=bool,help="true for forcingprocessor split",default=False)
    parser.add_argument("--realization_file", type=str,help="ngen realization file",required=True)

    args = parser.parse_args()    
    create_confs(args)