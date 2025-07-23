import argparse, json, os, copy, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
import platform
import psutil

PATTERN_VPU = r'\$VPU'

NWMURL_RUN_INPUT_MAPPING = {
    "SHORT_RANGE": 1,
    "MEDIUM_RANGE": 2,
    "MEDIUM_RANGE_NO_DA": 3,
    "LONG_RANGE": 4,
    "ANALYSIS_ASSIM": 5,
    "ANALYSIS_ASSIM_EXTEND": 6,
    "ANALYSIS_ASSIM_EXTEND_NO_DA": 7,
    "ANALYSIS_ASSIM_LONG": 8,
    "ANALYSIS_ASSIM_LONG_NO_DA": 9,
    "ANALYSIS_ASSIM_NO_DA": 10,
    "SHORT_RANGE_NO_DA": 11
}

NWMURL_NUM_HRS_MAPPING = {
    "SHORT_RANGE": 18,
    "MEDIUM_RANGE": 240,
    "ANALYSIS_ASSIM": 3,
    "ANALYSIS_ASSIM_EXTEND": 28,
}

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
    start_date = args.start_date
    end_date = args.end_date
    if start_date == 'DAILY':
        if args.end_date == "":
            end_date = datetime.now(timezone.utc).replace(hour=1,minute=0,second=0,microsecond=0).strftime('%Y%m%d%H%M')
        else:
            end_date = args.end_date
    config = {
        "globals": {
            "domain_name"   : args.domain_name,
            "start_date"    : start_date,
            "end_date"      : end_date,
            "data_dir"      : args.data_dir,
            "geopackage"    : args.geopackage_provided,
            "resource_dir"  : args.resource_path,
            "nprocs"        : args.nprocs,
            "ngen_bmi_confs" : args.ngen_bmi_confs,
            "realization"    : args.realization_provided, # this makes sure the realization in the output is the one the user provided directly
            "forcing_source" : args.forcing_source,
            "ngen_forcings"  : args.forcings,
            "s3_bucket"      : args.s3_bucket,
            "s3_prefix"      : args.s3_prefix
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

def config_class2envs(args, filename='config.env'):
    """
    Extracts values from args and writes them to a file in a format that can be sourced in a shell script.
    
    Parameters:
    args: The argparse Namespace object containing the configuration values.
    filename: The name of the file to write the environment variables to (default: 'config.env').
    use_export: If True, includes 'export' keyword for variables (default: True).
    """
    config = config_class2dict(args)  # Reuse the dict function to get structured config
    
    with open(filename, 'w') as f:
        # Write globals
        for key, value in config['globals'].items():
            env_key = key.upper()
            if value is not None:
                f.write(f'{env_key}="{value}"\n')
            else:
                f.write(f'{env_key}=\n')
        
        # Write subset
        for key, value in config['subset'].items():
            env_key = f'SUBSET_{key.upper()}'
            if value is not None:
                f.write(f'{env_key}="{value}"\n')
            else:
                f.write(f'{env_key}=\n')

def write_json(conf, out_dir, name):
    conf_path = Path(out_dir,name)
    if not os.path.exists(out_dir):
        os.system(f'mkdir -p {out_dir}')
    with open(conf_path,'w') as fp:
        json.dump(conf, fp, indent=2)
    return conf_path

def create_conf_nwm(args):    
    start = args.start_date
    end   = args.end_date  

    fcst_cycle = 0

    if "DAILY" in start:
        if end == "":
            start_dt = datetime.now(timezone.utc)
        else:
            start_dt = datetime.strptime(end,'%Y%m%d%H%M')   
        start_dt_exact = start_dt
        start_dt = start_dt.replace(hour=1,minute=0,second=0,microsecond=0)
        end_dt = start_dt
        num_hrs= 24
    else:
        start_dt = datetime.strptime(start,'%Y%m%d%H%M')
        end_dt   = datetime.strptime(end,'%Y%m%d%H%M')  
        num_hrs = ((end_dt - start_dt).seconds // 3600) + 1
    
    start_str_real = start_dt.strftime('%Y-%m-%d %H:%M:%S')
    end_str_real = end_dt.strftime('%Y-%m-%d %H:%M:%S')    
    start_str_nwm = start_dt.strftime('%Y%m%d%H%M') 
    end_str_nwm    = start_dt.strftime('%Y%m%d%H%M') 
                           
    if "RETRO" in args.forcing_source:                    
        if "V2" in args.forcing_source:
            urlbaseinput = 1
        if "V3" in args.forcing_source:
            urlbaseinput = 4         
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
        varinput = 5        

        if "HAWAII" in args.forcing_source:
            geoinput=2
        elif "PUERTORICO" in args.forcing_source:
            geoinput=3 
        else:
            geoinput=1

        if "NOMADS" in args.forcing_source:
            urlbaseinput = 1
            if "POSTPROCESSED" in args.forcing_source:
                urlbaseinput = 2         
        elif "NWM" in args.forcing_source: 
            urlbaseinput = 7
        elif len(args.forcing_source) == 0 and len(args.forcings) > 0:
            return {}, start_str_real, end_str_real # nextgen forcings have been supplied directly
        else:
            raise Exception(f'Forcing source {args.forcing_source} not understood')
        
        dt = 1
        ens_member = 0
        if "SHORT_RANGE" in args.forcing_source:
            runinput=1
            num_hrs=18
            # SHORT_RANGE_FCST
            # SHORT_RANGE_00
            fcst_cycle = int(args.forcing_source[-2:])
            # Adjust hours
            start_str_real = datetime.strftime(datetime.strptime(start_str_real,'%Y-%m-%d %H:%M:%S') + timedelta(hours=fcst_cycle),'%Y-%m-%d %H:%M:%S')
            end_str_real = datetime.strftime(datetime.strptime(end_str_real,'%Y-%m-%d %H:%M:%S') + timedelta(hours=fcst_cycle+num_hrs-1),'%Y-%m-%d %H:%M:%S')        
        elif "MEDIUM_RANGE" in args.forcing_source:
            runinput=2
            num_hrs=240   
            # MEDIUM_RANGE_FCST_MEMBER
            # MEDIUM_RANGE_00_3
            fcst_cycle = int(args.forcing_source[-4:-2])
            ens_member = int(args.forcing_source[-1])
            start_str_real = datetime.strftime(datetime.strptime(start_str_real,'%Y-%m-%d %H:%M:%S') + timedelta(hours=fcst_cycle),'%Y-%m-%d %H:%M:%S')
            end_str_real = datetime.strftime(datetime.strptime(end_str_real,'%Y-%m-%d %H:%M:%S') + timedelta(hours=fcst_cycle+num_hrs-1),'%Y-%m-%d %H:%M:%S')             
        elif "ANALYSIS_ASSIM" in args.forcing_source:
            if "EXTEND" in args.forcing_source:                
                runinput=6
                num_hrs=28
                dt=0 
                fcst_cycle = 16
                start_dt = start_dt - timedelta(hours=12)
                end_dt = end_dt + timedelta(hours=15)
                start_str_real = start_dt.strftime('%Y-%m-%d %H:%M:%S')
                end_str_real = end_dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                start_dt = start_dt - timedelta(hours=3)
                start_str_real = start_dt.strftime('%Y-%m-%d %H:%M:%S')
                runinput=5
                num_hrs=3
                
        else:
            runinput=2

        # apply a time shift if the requested init hour is after the current hour in utc, if so, date shift a day
        if "DAILY" in start and start_dt_exact.hour < fcst_cycle and args.end_date == "":
            start_str_real = datetime.strftime(datetime.strptime(start_str_real,'%Y-%m-%d %H:%M:%S') - timedelta(days=1),'%Y-%m-%d %H:%M:%S')
            end_str_real = datetime.strftime(datetime.strptime(end_str_real,'%Y-%m-%d %H:%M:%S') - timedelta(days=1),'%Y-%m-%d %H:%M:%S')
            start_str_nwm = datetime.strftime(datetime.strptime(start_str_nwm,'%Y%m%d%H%M') - timedelta(days=1),'%Y%m%d%H%M')
            end_str_nwm = datetime.strftime(datetime.strptime(end_str_nwm,'%Y%m%d%H%M') - timedelta(days=1),'%Y%m%d%H%M')                     
                          
        nwm_conf = {
            "forcing_type" : "operational_archive",
            "start_date"   : start_str_nwm,
            "end_date"     : end_str_nwm,
            "runinput"     : runinput,
            "varinput"     : varinput,
            "geoinput"     : geoinput,
            "meminput"     : ens_member,
            "urlbaseinput" : urlbaseinput,
            "fcst_cycle"   : [fcst_cycle],
            "lead_time"    : [x+dt for x in range(num_hrs)]
        }          

    return nwm_conf, start_str_real, end_str_real

def create_conf_fp(args,start_real):
    geo_base = args.geopackage.split('/')[-1]      
    if "RETRO" in args.forcing_source:
        filename = "retro_filenamelist.txt"
    else:
        filename = "filenamelist.txt"

    output_file_type = ["netcdf"]
    if len(args.s3_bucket) > 0:
        if "DAILY" in args.start_date: 
            args.s3_prefix = re.sub(r"\DAILY",datetime.strptime(start_real,'%Y-%m-%d %H:%M:%S').strftime('%Y%m%d'),args.s3_prefix)
        output_path  = f"s3://{args.s3_bucket}/{args.s3_prefix}"
    elif len(args.docker_mount) > 0:
        gpkg_file = [f"{args.docker_mount}/datastream-resources/config/{geo_base}"]
        output_path = f"{args.docker_mount}/ngen-run"  
    
    if len(args.forcing_split_vpu) > 0:
        template = f"/mounted_dir/nextgen_VPU_$VPU_weights.json"
        gpkg_file = []
        for jvpu in args.forcing_split_vpu.split(','):
            tmpl_cpy = copy.deepcopy(template)
            gpkg_file.append(re.sub(PATTERN_VPU, jvpu, tmpl_cpy))
    elif args.united_conus:
        gpkg_file = [f"/mounted_dir/conus_weights.parquet"]
    else:
        gpkg_file = [f"{args.docker_mount}/datastream-resources/config/{geo_base}"]

    fp_conf = {
        "forcing" : {
            "nwm_file"     : f"{args.docker_mount}/datastream-metadata/{filename}",
            "gpkg_file"    : gpkg_file,
        },
        "storage" : {
            "output_path"      : output_path,
            "output_file_type" : output_file_type,
        },
        "run" : {
            "verbose"        : True,
            "collect_stats"  : True,
            "nprocs"         : min(os.cpu_count(),args.nprocs),
        }
    }

    return fp_conf 

def create_confs(args):
    conf = config_class2dict(args)
    realization = args.realization

    if args.start_date != 'DAILY':
        start_dt = datetime.strptime(args.start_date,'%Y%m%d%H%M')
        end_dt   = datetime.strptime(args.end_date,'%Y%m%d%H%M')  
        start_real = start_dt.strftime('%Y-%m-%d %H:%M:%S')    
        end_real   = end_dt.strftime('%Y-%m-%d %H:%M:%S')  

    if args.forcings.endswith(".nc") or args.forcings.endswith(".tar.gz"):
        nwm_conf = {}
        fp_conf = {}
        fp_conf['forcing'] = args.forcings
        _, start_real, end_real = create_conf_nwm(args)
    elif os.path.exists(os.path.join(args.resource_path,"nwm-forcings")):
        nwm_conf = {}
        fp_conf  = create_conf_fp(args,start_real) 
    else:
        nwm_conf, start_real, end_real = create_conf_nwm(args)
        fp_conf  = create_conf_fp(args,start_real) 

    conf['nwmurl'] = nwm_conf 
    conf['forcingprocessor'] = nwm_conf    

    if os.path.exists(args.docker_mount):
        data_dir = Path(args.docker_mount)
    else:
        data_dir = Path(conf['globals']['data_dir'])

    ngen_config_dir = Path(data_dir,'ngen-run','config')
    if not os.path.exists(ngen_config_dir): os.system(f'mkdir -p {ngen_config_dir}')

    datastream_meta_dir = Path(data_dir,'datastream-metadata')    
    if not os.path.exists(datastream_meta_dir):os.system(f'mkdir -p {datastream_meta_dir}')

    write_json(nwm_conf,datastream_meta_dir,'conf_nwmurl.json')
    write_json(fp_conf,datastream_meta_dir,'conf_fp.json')
    write_json(conf,datastream_meta_dir,'conf_datastream.json')

    config_class2envs(args,filename = os.path.join(datastream_meta_dir,"datastream.env"))

    print(f'datastream metadata have been generated and placed here\n{datastream_meta_dir}')    
    
    with open(realization,'r') as fp:
        data = json.load(fp)
    write_json(data,datastream_meta_dir,'realization_user.json')

    data['time']['start_time'] = start_real
    data['time']['end_time']   = end_real  
    forcing_dict={}  
    if args.forcings.endswith(".tar.gz"):
        forcing_dict['file_pattern'] = ".*{{id}}.*.csv"
        forcing_dict['path'] = "./forcings"
        forcing_dict['provider'] = "CsvPerFeature"     
    elif args.forcings.endswith(".nc"):
        if "file_pattern" in data['global']['forcing']: del data['global']['forcing']['file_pattern']
        forcing_dict['provider'] = "NetCDF"
        forcing_dict['path'] = f"./forcings/{os.path.basename(args.forcings)}"   
    elif args.forcings == "":
        if "file_pattern" in data['global']['forcing']: del data['global']['forcing']['file_pattern']
        forcing_dict['provider'] = "NetCDF"
        forcing_dict['path'] = f"./forcings"   
        forcing_dict['file_pattern'] = ".*\\.nc"
    else:
        raise Exception(f'Forcing file {args.forcings} not understood, must be .nc or .tar.gz')

    data['global']['forcing'] = forcing_dict
    if "catchments" in data:
        for jcatch in data['catchments']:
            data['catchments'][jcatch]['forcing'] = forcing_dict
    
    write_json(data,ngen_config_dir,'realization.json')
    write_json(data,datastream_meta_dir,'realization_datastream.json')    


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--docker_mount", help="Path to data_dir mount within docker container",default="")
    parser.add_argument("--start_date", help="Set the start date",default=None)
    parser.add_argument("--end_date", help="Set the end date",default="")
    parser.add_argument("--data_dir", help="Set the data directory",default="")
    parser.add_argument("--geopackage",help="Lcoal path to geopackage file",default="")    
    parser.add_argument("--geopackage_provided",help="User provided path to geopackage file",default="")    
    parser.add_argument("--resource_path", help="Set the resource directory",default="")
    parser.add_argument("--forcings", help="Set the forcings file or directory",default="")
    parser.add_argument("--forcing_source", type=str,help="Option for source of forcings",default="NWM_V3")
    parser.add_argument("--subset_id_type", help="Set the subset ID type",default="")
    parser.add_argument("--subset_id", help="Set the subset ID",default="")
    parser.add_argument("--hydrofabric_version", help="Set the Hydrofabric version",default="")
    parser.add_argument("--nprocs", type=int,help="Maximum number of processes to use",default=os.cpu_count())
    parser.add_argument("--host_platform", type=str,help="Type of host",default="")
    parser.add_argument("--host_os", type=str,help="Operating system of host",default="")
    parser.add_argument("--domain_name", type=str,help="Name of spatial domain",default="Not Specified")
    parser.add_argument("--forcing_split_vpu", type=str,help="list of vpus",default="")
    parser.add_argument("--united_conus", type=bool,help="boolean to process entire conus from local weights file",default=False)
    parser.add_argument("--realization", type=str,help="local ngen realization file",required=True)
    parser.add_argument("--realization_provided", type=str,help="The exact path the user provided to their realization file",required=True)
    parser.add_argument("--s3_bucket", type=str,help="s3 bucket to write to",default="")
    parser.add_argument("--s3_prefix", type=str,help="s3 prefix to prepend to files",required="")    
    parser.add_argument("--ngen_bmi_confs", type=str,help="Path for user provided ngen bmi configs",required="")    

    args = parser.parse_args() 
    
    create_confs(args)
