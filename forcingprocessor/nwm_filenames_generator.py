import json
import nwmurl 
import argparse

def generate_nwmfiles(conf):
    forcing_type       = conf.get("forcing_type",None)
    start_date         = conf.get("start_date",None)
    end_date           = conf.get("end_date",None)
    runinput           = conf.get("runinput",None)
    varinput           = conf.get("varinput",None)
    geoinput           = conf.get("geoinput",None)
    meminput           = conf.get("meminput",None)
    object_type        = conf.get("object_type",None)
    selected_var_types = conf.get("selected_var_types",None)
    urlbaseinput       = conf.get("urlbaseinput",None)
    fcst_cycle         = conf.get("fcst_cycle",None)
    lead_time          = conf.get("lead_time",None)

    if forcing_type == 'operational_archive':
        nwmurl.generate_urls_operational(start_date, end_date, fcst_cycle, lead_time, varinput, geoinput, runinput, urlbaseinput, meminput, True)
    elif forcing_type == 'retrospective':
        nwmurl.generate_urls_retro(start_date, end_date, urlbaseinput, object_type, selected_var_types, True)        

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        dest="infile", type=str, help="A json containing user inputs to run nwmurl"
    )
    args = parser.parse_args()
    conf = json.load(open(args.infile))
    generate_nwmfiles(conf)