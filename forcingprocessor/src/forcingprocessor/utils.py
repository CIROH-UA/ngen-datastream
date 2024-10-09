from datetime import datetime
import numpy as np
from datetime import timezone
import psutil

nwm_variables = [
        "U2D",
        "V2D",
        "LWDOWN",
        "RAINRATE",
        "RAINRATE",
        "T2D",
        "Q2D",
        "PSFC",
        "SWDOWN",
    ]

ngen_variables = [
        "UGRD_10maboveground",
        "VGRD_10maboveground",
        "DLWRF_surface",
        "APCP_surface",
        "precip_rate",
        "TMP_2maboveground",        
        "SPFH_2maboveground",
        "PRES_surface",
        "DSWRF_surface",
    ] 

def get_window(weights_json):
    """
    Providing window on weights

    weights_json : datastream weights where each key is the catchment id and the values are the weights
    """
    x_min_list = []
    x_max_list = []
    y_min_list = []
    y_max_list = []
    idx_2d = []
    for jcat in weights_json:
        indices = weights_json[jcat][0]
        idx_2d=np.unravel_index(indices, (1, 4608, 3840), order='F')
        x_min_list.append(np.min(idx_2d[1]))
        x_max_list.append(np.max(idx_2d[1]))
        y_min_list.append(np.min(idx_2d[2]))
        y_max_list.append(np.max(idx_2d[2]))   
    x_min=np.min(x_min_list)   
    x_max=np.max(x_max_list)   
    y_min=np.min(y_min_list)   
    y_max=np.max(y_max_list) 

    return x_min, x_max, y_min, y_max

def log_time(label, log_file):
    timestamp = datetime.now(timezone.utc).astimezone().strftime('%Y%m%d%H%M%S')
    with open(log_file, 'a') as f:
        f.write(f"{label}: {timestamp}\n")

def report_usage():
    usage_ram   = psutil.virtual_memory()[3]/1000000000
    percent_ram = psutil.virtual_memory()[2]
    percent_cpu = psutil.cpu_percent()
    print(f'\nCurrent RAM usage (GB): {usage_ram:.2f}, {percent_ram:.2f}%\nCurrent CPU usage : {percent_cpu:.2f}%')
    return usage_ram, percent_ram, percent_cpu        

def convert_url2key(nwm_file,fs_type):
    bucket_key = ""
    _nc_file_parts = nwm_file.split('/')
    layers = _nc_file_parts[3:]
    for jlay in layers:
        if jlay == layers[-1]:
            bucket_key += jlay
        else:
            bucket_key += jlay + "/"
    if fs_type == "google":
        bucket = _nc_file_parts[3]
    elif fs_type == 's3':
        bucket = _nc_file_parts[2]
    
    return bucket, bucket_key