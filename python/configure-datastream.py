import argparse, json, os
from datetime import datetime, timedelta
from pathlib import Path
import pytz as tz

def write_json(conf, out_dir, name):
    conf_path = Path(out_dir,name)
    with open(conf_path,'w') as fp:
        json.dump(conf, fp, indent=2)
    return conf_path

def create_ds_confs_daily(conf, today, tomorrow):
    
    conf['globals']['start_date'] = today
    conf['globals']['end_date']   = tomorrow

    fp_conf = {
        "forcing" : {
            "start_date"   : conf['globals']['start_date'],
            "end_date"     : conf['globals']['end_date'],
            "nwm_file"     : "/mounted_dir/datastream-resources/filenamelist.txt",
            "weight_file"  : "/mounted_dir/datastream-resources/weights.json",
        },
        "storage" : {
            "storage_type"     : "local",
            "output_bucket"    : "",
            "output_path"      : "/mounted_dir/ngen-run",
            "output_file_type" : "csv",
        },
        "run" : {
            "verbose"       : True,
            "collect_stats" : True
        }
    }

    nwm_conf = {
        "forcing_type" : "operational_archive",
        "start_date"   : today,
        "end_date"     : today, # If we specify this as tomorrow, we will get 2 days worth of data, just how nwmurl works
        "runinput"     : 2,
        "varinput"     : 5,
        "geoinput"     : 1,
        "meminput"     : 0,
        "urlbaseinput" : 7,
        "fcst_cycle"   : [0],
        "lead_time"    : [x+1 for x in range(24)]
    }

    conf['forcingprcoessor'] = fp_conf
    conf['nwmurl'] = nwm_conf

    return conf, fp_conf, nwm_conf

def create_confs(conf):
    
    if conf['globals']['start_date'] == "DAILY":
        now = datetime.now(tz.timezone('US/Eastern'))
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        
        today_ds_confs = today.strftime('%Y%m%d%H%M')
        tomorrow_ds_confs = tomorrow.strftime('%Y%m%d%H%M')

        today_realization =  today.strftime('%Y-%m-%d %H:%M:%S')
        tomorrow_realization =  tomorrow.strftime('%Y-%m-%d %H:%M:%S')

        if conf['globals'].get('data_dir',"") == "":
            conf['globals']['data_dir'] = today.strftime('%Y%m%d')

        if conf['globals'].get('relative_dir',"") == "":
            conf['globals']['relative_to'] = str(Path(Path(Path(__file__).resolve()).parents[1],"data"))

        data_dir = Path(conf['globals']['relative_to'],conf['globals']['data_dir'])
        ngen_config_dir = Path(data_dir,'ngen-run','config')
        datastream_config_dir = Path(data_dir,'datastream-configs')
        resources_dir = Path(data_dir,'datastream-resources')
        resources_config_dir = Path(resources_dir,'ngen-configs')        
        
        ds_conf, fp_conf, nwm_conf = create_ds_confs_daily(conf, today_ds_confs, tomorrow_ds_confs)

        realization_file = None
        for path, _, files in os.walk(ngen_config_dir):
            for jfile in files:
                jfile_path = os.path.join(path,jfile)
                if jfile_path.find('realization') >= 0: 
                        realization_file = jfile_path
                        break

        if not realization_file: raise Exception(f"Cannot find realization file in {ngen_config_dir}")

        with open(realization_file,'r') as fp:
            data = json.load(fp)

        template_realization = Path(resources_config_dir,"realization.json")
        template_realization_rename = Path(resources_config_dir,"realization_template.json")
        os.system(f'mv {template_realization} {template_realization_rename}')

        data['time']['start_time'] = today_realization
        data['time']['end_time']   = tomorrow_realization
        write_json(data,ngen_config_dir,'realization.json')
        
    else: 
        nwm_conf = conf['nwmurl']
        fp_conf  = conf['forcingprocessor']
        if "subsetting" in conf:
            ds_conf = {conf['globals'],conf['subsetting']}
        else:
            ds_conf = conf['globals']
        
    write_json(nwm_conf,datastream_config_dir,'conf_nwmurl.json')
    write_json(fp_conf,datastream_config_dir,'conf_fp.json')
    write_json(ds_conf,datastream_config_dir,'conf_datastream.json')

    print(f'\ndatastream configs have been generated and placed here\n{datastream_config_dir}\n')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        dest="infile", type=str, help="A json containing user inputs to run ngen-datastream"
    )
    args = parser.parse_args()

    if args.infile[0] == '{':
        conf = json.loads(args.infile)
    else:
        if 's3' in args.infile:
            os.system(f'wget {args.infile}')
            filename = args.infile.split('/')[-1]
            conf = json.load(open(filename))
        else:
            conf = json.load(open(args.infile))

    create_confs(conf)
