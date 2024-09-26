import argparse, json, os, copy, re
from datetime import datetime, timedelta
from pathlib import Path
import pytz as tz
import platform
import psutil

PATTERN_VPU = r'\$VPU'

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

def create_conf_fp(start,end,nprocs,docker_mount,forcing_split_vpu,retro_or_op,geo_base,hf_version):
    if retro_or_op == "retrospective":
        filename = "retro_filenamelist.txt"
    else:
        filename = "filenamelist.txt"
    
    if len(forcing_split_vpu) > 0:
        template = "https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/{hf_version}/nextgen/conus_forcing-weights/vpuid%3D$VPU/part-0.parquet"
        gpkg_file = []
        for jvpu in forcing_split_vpu:
            tmpl_cpy = copy.deepcopy(template)
            gpkg_file.append(re.sub(PATTERN_VPU, jvpu, tmpl_cpy))

        output_path  = f"s3://ngen-datastream/forcings/{hf_version}/{start}-{end}"
        output_file_type = ["netcdf"]
    else:
        gpkg_file = [f"{docker_mount}/datastream-resources/config/{geo_base}"]
        output_path = f"{docker_mount}/ngen-run"
        output_file_type = ["netcdf"]

    fp_conf = {
        "forcing" : {
            "nwm_file"     : f"{docker_mount}/datastream-metadata/{filename}",
            "gpkg_file"    : gpkg_file,
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

def create_conf_nwm(start, end, retro_or_op,runinput,urlbaseinput):

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
            "runinput"     : runinput,
            "varinput"     : 5,
            "geoinput"     : 1,
            "meminput"     : 0,
            "urlbaseinput" : urlbaseinput,
            "fcst_cycle"   : [0],
            "lead_time"    : [x+1 for x in range(num_hrs)]
        }

    return nwm_conf  

def create_confs(args):
    forcing_split_vpu = args.forcing_split_vpu.split(',')  
    conf = config_class2dict(args)
    realization = args.realization_file
    geo_base = args.gpkg.split('/')[-1]      
        
    if "DAILY" in conf['globals']['start_date']:
        retro_or_op = "operational" 
        urlbaseinput = 7
        duration     = 24
        runinput     = 2
        if conf['globals']['end_date'] == "":
            start_date = datetime.now(tz.timezone('US/Eastern'))
        else:
            # allows for a "daily" run that is not the current date
            start_date = datetime.strptime(conf['globals']['end_date'],'%Y%m%d%H%M')
        retro_or_op="operational"

        if "SHORT_RANGE" in conf['globals']['start_date']: 
            duration = 18
            runinput = 1
        if "MEDIUM_RANGE" in conf['globals']['start_date']: 
            duration = 240
            runinput = 2

        start_datetime0   = start_date.replace(hour=1, minute=0, second=0, microsecond=0)
        end_datetime      = start_datetime0 + timedelta(hours=duration-1)     
        start_str         = start_datetime0.strftime('%Y%m%d%H%M')
        start_realization = start_datetime0.strftime('%Y-%m-%d %H:%M:%S')        
        end_str           = end_datetime.strftime('%Y%m%d%H%M')
        end_realization   = end_datetime.strftime('%Y-%m-%d %H:%M:%S')

        nwm_conf = create_conf_nwm(start_str, end_str, retro_or_op, runinput, urlbaseinput)
        fp_conf  = create_conf_fp(start_str, end_str, conf['globals']['nprocs'],args.docker_mount,forcing_split_vpu,retro_or_op,geo_base,args.hydrofabric_version) 

    else: 
        if "OPERATIONAL" in args.forcing_source:    
            retro_or_op = "operational"   
            runinput = 2      
            if "V3" in args.forcing_source:
                urlbaseinput = 7
            if "NOMADS" in args.forcing_source:
                urlbaseinput = 1                   
        elif "RETRO" in args.forcing_source:   
            retro_or_op = "retrospective"   
            runinput = None       
            if "V2" in args.forcing_source:
                urlbaseinput = 1
            if "V3" in args.forcing_source:
                urlbaseinput = 4 
        else:
            raise Exception(f'forcing_source not understood, lacks either OPERATIONAL or RETRO')

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
            fp_conf  = create_conf_fp(start, end, conf['globals']['nprocs'], args.docker_mount, forcing_split_vpu,retro_or_op,geo_base,args.hydrofabric_version) 
        else:
            nwm_conf = create_conf_nwm(start,end, retro_or_op,runinput,urlbaseinput)
            fp_conf  = create_conf_fp(start, end, conf['globals']['nprocs'], args.docker_mount, forcing_split_vpu,retro_or_op,geo_base,args.hydrofabric_version) 

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
    parser.add_argument("--forcing_split_vpu", type=str,help="true for forcingprocessor split",default="")
    parser.add_argument("--realization_file", type=str,help="ngen realization file",required=True)

    args = parser.parse_args()      
    create_confs(args)