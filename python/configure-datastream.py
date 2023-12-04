import argparse, json, os, datetime
from pathlib import Path

def create_nwmurl_conf(conf, out_dir):
    nwm_conf = conf['nwmurl']
    nwm_conf['start_date'] = conf['globals']['start_date']
    nwm_conf['end_date']   = conf['globals']['end_date']
    conf_name = 'conf_nwmurl.json'
    conf_path = Path(out_dir,conf_name)
    with open(conf_path,'w') as fp:
        json.dump(nwm_conf, fp)

    return conf_path

def create_fp_conf(conf, out_dir):
    fp_conf = conf['forcingprocessor']
    fp_conf['forcing'] = {}
    fp_conf['forcing']['start_date']   = conf['globals']['start_date']
    fp_conf['forcing']['end_date']     = conf['globals']['end_date']
    fp_conf['forcing']['nwm_file']     = "/mounted_dir/datastream-resources/filenamelist.txt"
    fp_conf['forcing']['weight_file']  = "/mounted_dir/datastream-resources/weights.json"
    fp_conf['storage']['storage_type'] = "local"
    fp_conf['storage'] = {}
    fp_conf['storage']['output_bucket']    = "/mounted_dir/ngen-run"
    fp_conf['storage']['output_path']      = "/mounted_dir/ngen-run"
    fp_conf['storage']['output_file_type'] = "csv"
    fp_conf['run'] = {}
    fp_conf['run']['verbose'] = False
    conf_name = 'conf_fp.json'
    conf_path = Path(out_dir,conf_name)
    with open(conf_path,'w') as fp:
        json.dump(fp_conf, fp)

    return conf_path

def create_confs(conf):
    if conf['globals']['start_date'] == "DAILY":
        date = datetime.datetime.now()
        date = date.strftime('%Y%m%d')
        hourminute = '0000'
        
        conf['globals']['start_date'] = date + hourminute
        conf['globals']['end_date']   = date + hourminute

        # conf['nwmurl']['lead_time'] = [x+1 for x in range(24)]

    if "relative_to" in conf['globals'].keys():
        out_dir = Path(conf['globals']['relative_to'],conf['globals']['data_dir'])
    else:
        out_dir = conf['globals']['data_dir']
    out_dir = Path(out_dir,'datastream-configs')

    create_nwmurl_conf(conf,out_dir)
    create_fp_conf(conf,out_dir)

    conf_name = 'conf_datastream.json'
    conf_path = Path(out_dir,conf_name)
    with open(conf_path,'w') as fp:
        json.dump(conf, fp)

    print(f'\ndatastream configs have been generated and placed here\n{out_dir}\n')

if __name__ == "__main__":
    # Take in user config
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
