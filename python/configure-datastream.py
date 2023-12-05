import argparse, json, os, datetime
from pathlib import Path

def write_conf(conf, out_dir, name):
    conf_path = Path(out_dir,name)
    with open(conf_path,'w') as fp:
        json.dump(conf, fp)
    return conf_path

def create_confs_daily(conf):
    date = datetime.datetime.now()
    date = date.strftime('%Y%m%d')
    hourminute = '0000'
    
    conf['globals']['start_date'] = date + hourminute
    conf['globals']['end_date']   = date + hourminute

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
            "verbose" : False,
            "collect_stats" : True
        }
    }

    nwm_conf = {
        "forcing_type" : "operational_archive",
        "start_date"   : conf['globals']['start_date'],
        "end_date"     : conf['globals']['end_date'],
        "runinput"     : 1,
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
        ds_conf, fp_conf, nwm_conf = create_confs_daily(conf)

    if "relative_to" in conf['globals'].keys():
        out_dir = Path(conf['globals']['relative_to'],conf['globals']['data_dir'])
    else:
        out_dir = conf['globals']['data_dir']
    out_dir = Path(out_dir,'datastream-configs')

    write_conf(nwm_conf,out_dir,'conf_fp.json')
    write_conf(fp_conf,out_dir,'conf_fp.json')
    write_conf(ds_conf,out_dir,'conf_datastream.json')

    print(f'\ndatastream configs have been generated and placed here\n{out_dir}\n')

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
