import pandas as pd
import argparse, os, json, sys, re
import requests
import s3fs
import gcsfs
from pathlib import Path
import numpy as np
import xarray as xr
import time
import boto3
from io import BytesIO, TextIOWrapper
import concurrent.futures as cf
import multiprocessing as mp
import ctypes
from datetime import datetime, timezone
import psutil
import gzip
import tarfile, tempfile
import multiprocessing as mp
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
from forcingprocessor.weights_hf2ds import hydrofabric2datastream_weights

global nwm_variables
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

global ngen_variables
ngen_variables = [
    "UGRD_10maboveground",
    "VGRD_10maboveground",
    "DLWRF_surface",
    "APCP_surface",
    "precip_rate",  # HACK RAINRATE * 3600
    "TMP_2maboveground",        
    "SPFH_2maboveground",
    "PRES_surface",
    "DSWRF_surface",
] 

def log_time(label, log_file):
    timestamp = datetime.now(timezone.utc).astimezone().strftime('%Y%m%d%H%M%S')
    with open(log_file, 'a') as f:
        f.write(f"{label}: {timestamp}\n")

def convert_url2key(nwm_file,fs_type):
    bucket_key = ""
    _nc_file_parts = nwm_file.split('/')
    layers = _nc_file_parts[3:]
    for jlay in layers:
        bucket_key += "/" + jlay 

    if fs_type == 's3':
        bucket_key = _nc_file_parts[2][:-17] + bucket_key
    elif fs_type == 'google':
        bucket_key = "gs:/" + bucket_key
    if "s3://" in nwm_file: bucket_key = bucket_key[1:]
    bucket = _nc_file_parts[2]
    return bucket, bucket_key

def distribute_work(items,nprocs):
    """
    Distribute items evenly between processes, round robin
    """
    items_per_proc = [0 for x in range(nprocs)]
    for j in range(len(items)):
        k = j % nprocs
        items_per_proc[k] = items_per_proc[k] + 1
    return items_per_proc

def load_balance(items_per_proc,launch_delay,single_ex, exec_count):
    """
    Python takes a couple seconds to launch a process so if this script is launched with 10's
    of processes, it may not be optimal to distribute the work evenly.
    This function minimizes projected processing time

    items_per_proc : list of length number of processes with each element representing the number of items the process has been assigned
    launch_delay   : time in seconds it takes python to launch the function
    single_ex      : time in seconds it takes to process 1 item
    exec_count     : number of items processed per execution

    """
    nprocs = len(items_per_proc)
    nitems = np.sum(items_per_proc)
    completion_time = [single_ex * x / exec_count + launch_delay*j for j, x in enumerate(items_per_proc)]
    while True:        
        if len(np.nonzero(items_per_proc)[0]) > 0: break
        max_time = max(completion_time)
        max_loc = completion_time.index(max_time)
        min_time = min(completion_time)
        min_loc = completion_time.index(min_time)
        if max_time - min_time > single_ex:
            items_per_proc[max_loc] -= 1
            items_per_proc[min_loc] += 1
        else:
            break
        completion_time = [single_ex * x / exec_count + launch_delay*j for j, x in enumerate(items_per_proc)]

    completion_time = [single_ex * x / exec_count + j for j, x in enumerate(items_per_proc)]
    global ntasked
    ntasked = len(np.nonzero(items_per_proc)[0])
    if nprocs > ntasked: 
        if ii_verbose: print(f'Not enough work for {nprocs} requested processes, downsizing to {ntasked}')
        nprocs = ntasked 
        completion_time = completion_time[:ntasked]
        items_per_proc = items_per_proc[:ntasked]
    if ii_verbose: print(f'item distribution {items_per_proc}')
    return items_per_proc

def report_usage():
    usage_ram   = psutil.virtual_memory()[3]/1000000000
    percent_ram = psutil.virtual_memory()[2]
    percent_cpu = psutil.cpu_percent()
    if ii_verbose: print(f'\nCurrent RAM usage (GB): {usage_ram:.2f}, {percent_ram:.2f}%\nCurrent CPU usage : {percent_cpu:.2f}%')
    return usage_ram, percent_ram, percent_cpu

def multiprocess_data_extract(files,nprocs,weights_json,fs):
    """
    Sets up the multiprocessing pool for forcing_grid2catchment and returns the data and time axis ordered in time.

    Parameters:
        files (list): List of files to be processed.
        nprocs (int): Number of processes to be used.
        weights_json (dict): Dictionary containing catchment weights.
        fs (s3 filesystem): s3fs

    Returns:
        data_array (numpy.ndarray): Concatenated array containing the extracted data.
        t_ax_local (list): List of time axes corresponding to the extracted data.
    """
    launch_time     = 0.05
    cycle_time      = 35
    files_per_cycle = 1
    files_per_proc  = distribute_work(files,nprocs)
    files_per_proc  = load_balance(files_per_proc,launch_time,cycle_time,files_per_cycle)
    nprocs          = len(files_per_proc)

    start  = 0
    nfiles = len(files)
    files_list = []
    idx_list   = []    
    fs_list    = []
    for i in range(nprocs):
        end = min(start + files_per_proc[i],nfiles)
        files_list.append(files[start:end])
        idx_list.append(np.arange(start,end))
        fs_list.append(fs)
        start = end

    data_ax = []
    t_ax_local = []
    with cf.ProcessPoolExecutor(max_workers=nprocs) as pool:
        for results in pool.map(
        forcing_grid2catchment,
        files_list,
        idx_list,
        fs_list
        ):
            data_ax.append(results[0])
            t_ax_local.append(results[1])            

    print(f'Processes have returned')
    del weights_json
    data_array = np.concatenate(data_ax)
    t_ax_local = [item for sublist in t_ax_local for item in sublist]
  
    return data_array, t_ax_local

def forcing_grid2catchment(nwm_files: list, idx_list: list, fs=None):
    """
    Retrieve catchment level data from national water model files

    Inputs:
    nwm_files: list of filenames (urls for remote, local paths otherwise),
    fs: an optional file system for cloud storage reads

    Outputs:
    df_by_t : (returned for local files) a list (in time) of forcing data. Note that this list may not be consistent in time
    t : model_output_valid_time for each

    Globals:
    weights_json : dictionary with catchment-ids as keys and values are a list of two items, indices and coverage

    """
    topen = 0
    txrds = 0
    tfill = 0    
    tdata = 0    
    t_list = []
    nfiles = len(nwm_files)
    nvar = len(nwm_variables)

    dx = x_max - x_min + 1
    dy = y_max - y_min + 1
    print(f'{x_min} {x_max} {y_min} {y_max} {dx} {dy}')

    if fs_type == 'google' : fs = gcsfs.GCSFileSystem() 
    id = os.getpid()
    if ii_verbose: print(f'Process #{id} extracting data from {nfiles} files',end=None,flush=True)
    data_list = []
    for j, nwm_file in enumerate(nwm_files):
        t0 = time.perf_counter()        
        eng    = "h5netcdf"
        if fs:
            if nwm_file.find('https://') >= 0: _, bucket_key = convert_url2key(nwm_file,fs_type)
            else: bucket_key = nwm_file
            file_obj   = fs.open(bucket_key, mode='rb')
        elif 'https://' in nwm_file:
            response = requests.get(nwm_file)
            file_obj = BytesIO(response.content)
        else:
            file_obj = nwm_file

        topen += time.perf_counter() - t0
        t0 = time.perf_counter()  
        with xr.open_dataset(file_obj, engine=eng) as nwm_data:
            txrds += time.perf_counter() - t0
            t0 = time.perf_counter()                     
            shp = nwm_data["U2D"].shape   
            data_allvars = np.zeros(shape=(nvar, dy, dx), dtype=np.float32)       
            for var_dx, jvar in enumerate(nwm_variables):                
                data_allvars[var_dx, :, :] = np.flip(np.squeeze(nwm_data[jvar].isel(x=slice(x_min, x_max + 1), y=slice(shp[1] - y_max, shp[1] - y_min + 1))),0)
            time_splt = nwm_data.attrs["model_output_valid_time"].split("_")
            t = time_splt[0] + " " + time_splt[1]
            t_list.append(t)       
        del nwm_data
        tfill += time.perf_counter() - t0        

        t0 = time.perf_counter()
        data_allvars = data_allvars.reshape(nvar, dx*dy)
        ncatch = len(weights_json)
        data_array = np.zeros((nvar,ncatch), dtype=np.float32)
        jcatch = 0
        for _, value in weights_json.items(): 
            weights = value[0]
            coverage = np.array(value[1])
            coverage_mat = np.repeat(coverage[None,:],nvar,axis=0)

            weights_dx, weights_dy = np.unravel_index(weights, (shp[2], shp[1]), order='F')
            weights_dx_shifted = list(weights_dx - x_min)
            weights_dy_shifted = list(weights_dy - y_min)
            weights_window = np.ravel_multi_index(np.array([weights_dx_shifted,weights_dy_shifted]),(dx,dy),order='F')   
            jcatch_data_mask = data_allvars[:,weights_window]     

            weight_sum = np.sum(coverage)
            data_array[:,jcatch] = np.sum(coverage_mat * jcatch_data_mask ,axis=1) / weight_sum  
            jcatch += 1  

        del data_allvars
        data_list.append(data_array)
        tdata += time.perf_counter() - t0
        ttotal = topen + txrds + tfill + tdata
        if ii_verbose: print(f'\nAverage time for:\nfs open file: {topen/(j+1):.2f} s\nxarray open dataset: {txrds/(j+1):.2f} s\nfill array: {tfill/(j+1):.2f} s\ncalculate catchment values: {tdata/(j+1):.2f} s\ntotal {ttotal/(j+1):.2f} s\npercent complete {100*(j+1)/nfiles:.2f}', end=None,flush=True)
        report_usage()

    if ii_verbose: print(f'Process #{id} completed data extraction, returning data to primary process',flush=True)
    return [data_list, t_list]

def multiprocess_write(data,t_ax,catchments,nprocs,out_path,ii_append):
    """
    Sets up the process pool for write_data.

    Parameters:
        data (numpy.ndarray): 3D array containing the data to be written.
        t_ax (numpy.ndarray): Array representing the time axis of the data.
        catchments (iterable): List of catchment identifiers.
        nprocs (int): Number of processes to be used for writing data.
        out_path (str): Path where the output files will be saved.
        ii_append (bool): Flag indicating whether to append to existing files.

    Returns:
        flat_ids (list): Flattened list of catchment identifiers.
        flat_dfs (list): Flattened list of pandas DataFrames.
        flat_filenames (list): Flattened list of filenames.
        flat_file_sizes (list): Flattened list of file sizes in MB.
        flat_file_sizes_zipped (list): Flattened list of file sizes after compression in MB.
    """

    launch_time          = 0.05
    cycle_time           = 1
    catchments_per_cycle = 200
    catchments_per_proc  = distribute_work(catchments,nprocs)
    catchments_per_proc  = load_balance(catchments_per_proc,launch_time,cycle_time,catchments_per_cycle)

    ntasked = len(np.nonzero(catchments_per_proc)[0])
    if nprocs > ntasked: 
        if ii_verbose: print(f'Not enough work for {nprocs} requested processes, downsizing to {ntasked}')
    
    ncatchments           = len(catchments)
    out_path_list         = []
    append_list           = []
    print_list            = []
    worker_time_list      = []
    worker_data_list      = []
    worker_catchment_list = []
    worker_catchments     = {}
    
    i = 0
    count = 0
    start = 0
    end   = 0
    ii_print = False
    for j, jcatch in enumerate(catchments):
        worker_catchments[jcatch] = jcatch      
        count +=1     
        if count == catchments_per_proc[i] or j == ncatchments - 1:
            if len(worker_catchment_list) == ntasked - 1 : ii_print = True

            end = min(start + catchments_per_proc[i],ncatchments)
            worker_data = data[:,:,start:end]
            worker_data_list.append(worker_data)
            start = end

            worker_catchment_list.append(worker_catchments)
            out_path_list.append(out_path)
            append_list.append(ii_append)
            print_list.append(ii_print)
            worker_time_list.append(t_ax)

            worker_catchments = {}
            count = 0
            
            i += 1

    ids = []
    dfs = []
    filenames = []
    file_sizes_MB = []
    file_sizes_zipped_MB = []
    tar_list = []
    with cf.ProcessPoolExecutor(max_workers=nprocs) as pool:
         for results in pool.map(
        write_data,
        worker_data_list,
        worker_time_list,
        worker_catchment_list,
        out_path_list,
        append_list,  
        print_list,      
        ):
            ids.append(results[0])
            dfs.append(results[1])
            filenames.append(results[2])
            file_sizes_MB.append(results[3])
            file_sizes_zipped_MB.append(results[4])
            tar_list.append(results[5])

    print(f'\n\nGathering data from write processes...')

    flat_ids = []
    flat_dfs = []
    flat_filenames = []
    flat_file_sizes = []
    flat_file_sizes_zipped = []
    flat_tar = []

    while ids:
        flat_ids.extend(ids.pop(0))
        flat_dfs.extend(dfs.pop(0))
        flat_filenames.extend(filenames.pop(0))
        flat_file_sizes.extend(file_sizes_MB.pop(0))
        flat_file_sizes_zipped.extend(file_sizes_zipped_MB.pop(0))
        flat_tar.extend(tar_list.pop(0))

    return flat_ids, flat_dfs, flat_filenames, flat_file_sizes, flat_file_sizes_zipped, flat_tar

def write_data(
        data,
        t_ax,
        catchments,
        out_path,
        ii_append,
        ii_print  
):
    """
    Write catchment forcing data to csv or parquet if requested. Also responsible for 
    creating/formatting data in memory for tar writing and metadata collection.

    Args:
        data: Input data to be written (numpy array)
        t_ax: Time axis data (numpy array)
        catchments: List of catchment identifiers
        out_path: Output path for writing files
        ii_append: Flag for appending to existing files
        ii_print: Flag for printing progress information

    Returns:
        forcing_cat_ids: List of catchment identifiers
        dfs: List of pandas DataFrames
        filenames: List of filenames
        file_size_MB: List containing the size of each file in MB
        file_zipped_size_MB: List containing the size of each zipped file in MB
    """
    s3_client = boto3.session.Session().client("s3")   

    nfiles = len(catchments)
    id = os.getpid()
    if ii_verbose: print(f'{id} writing {nfiles} dataframes to {output_file_type}', end=None, flush =True)

    forcing_cat_ids = []
    tar_list = []
    dfs = []
    filenames = []
    filename  = ""
    write_int = 400
    t_df      = 0
    t_buff    = 0
    t_put     = 0    
    
    if storage_type == 's3':
        bucket, key_prefix = convert_url2key(out_path, storage_type)

    t00 = time.perf_counter()
    for j, jcatch in enumerate(catchments):

        t0 = time.perf_counter()
        df_data = data[:,:,j]
        df     = pd.DataFrame(df_data,columns=ngen_variables)
        df.insert(0,"time",t_ax)
        t_df += time.perf_counter() - t0
        
        cat_id = jcatch.split("-")[1]
        forcing_cat_ids.append(cat_id)

        t0 = time.perf_counter()

        if "parquet" in output_file_type or "csv" in output_file_type :
            if storage_type == 's3':            
                bucket, key_prefix = convert_url2key(out_path, storage_type)                            
                if "parquet" in output_file_type:
                    buf = BytesIO()
                    filename = key_prefix + f"/cat-{cat_id}.parquet"
                    if ii_append:
                        df_bucket = pd.read_parquet(s3_client.get_object(Bucket = bucket, Key = filename).get("Body"))
                        df = pd.concat([df_bucket,df])
                        del df_bucket
                    df.to_parquet(buf, index=False)                
                elif "csv" in output_file_type:
                    buf = BytesIO()
                    filename = key_prefix + f"/cat-{cat_id}.csv"
                    if ii_append:
                        df_bucket = pd.read_csv(s3_client.get_object(Bucket = bucket, Key = filename).get("Body"))
                        df = pd.concat([df_bucket,df])
                        del df_bucket    
                    df.to_csv(buf, index=False)

                t_buff += time.perf_counter() - t0
                t0 = time.perf_counter()                
                buf.seek(0)                  
                s3_client.put_object(Bucket=bucket, Key=filename, Body=buf.getvalue()) 
                t_put += time.perf_counter() - t0            

            elif storage_type == 'local':                
                if "parquet" in output_file_type:
                    filename = str((out_path/Path(f"cat-{cat_id}.parquet" )).resolve())
                    if ii_append:
                        df_bucket = pd.read_parquet(filename)
                        df = pd.concat([df_bucket,df])
                        del df_bucket  
                    df.to_parquet(filename, index=False)                
                elif "csv" in output_file_type:
                    filename = str((out_path/Path(f"cat-{cat_id}.csv" )).resolve())
                    if ii_append:
                        df_bucket = pd.read_csv(filename)
                        df = pd.concat([df_bucket,df])
                        del df_bucket  
                    df.to_csv(filename, index=False)      
        else: 
            filename = f"./cat-{cat_id}.csv"

        dfs.append(df)     
        filenames.append(str(Path(filename).name))          

        if "tar" in output_file_type:
            buf = BytesIO()
            df.to_csv(buf, index=False)
            buf.seek(0)
            tar_list.append(buf)

        if j == 0:
            if not os.path.exists(filename):
                filename = f"./cat-{cat_id}.csv"
                df.to_csv(filename, index=False)  
                file_size_MB = os.path.getsize(filename) / 1000000
                os.remove(filename)
            else:
                file_size_MB = os.path.getsize(filename) / 1000000

            pattern = r'\.\w+$'
            filename_zip = re.sub(pattern, '.zip', filename)
            with gzip.GzipFile(filename_zip, mode='w') as zipped_file:
                df.to_csv(TextIOWrapper(zipped_file, 'utf8'), index=False) 
            file_zipped_size_MB = os.path.getsize(filename_zip) / 1000000    
            os.remove(filename_zip)            

        if ii_print and ii_verbose:
            if (j + 1) % write_int == 0 or j == nfiles - 1:
                t_accum = time.perf_counter() - t00
                rate = ((j+1)*ntasked/t_accum)
                bytes2bits = 8
                bandwidth_Mbps = rate * file_size_MB * ntasked * bytes2bits
                estimate_total_time = nfiles * ntasked / rate
                report_usage()
                msg = f"\n{(j+1)*ntasked} files written out of {nfiles*ntasked}\n"
                msg += f"rate             {rate:.2f} files/s\n"
                msg += f"df conversion    {t_df:.2f}s\n"
                if storage_type == "s3": msg += f"buff             {t_buff:.2f}s\n"
                if storage_type == "s3": msg += f"put              {t_put:.2f}s\n"                
                msg += f"estimated total write time {estimate_total_time:.2f}s\n"
                msg += f"progress                   {(j+1)/nfiles*100:.2f}%\n"
                msg += f"Bandwidth (all processs)   {bandwidth_Mbps:.2f} Mbps"
                print(msg,flush=True)

    return forcing_cat_ids, dfs, filenames, [file_size_MB], [file_zipped_size_MB], tar_list

def write_tar(tar_buffs,jcatchunk,catchments,filenames):
    """
    Write DataFrames to a tar archive and upload to S3 or save locally as a compressed tar file.

    Args:
        dfs: List of pandas DataFrames to be archived.
        jcatchunk: Identifier for the chunk of catchments.
        catchments: List of catchments.
        filenames: List of filenames corresponding to the DataFrames.

    Returns:
        None
    """
    print(f'Writing {jcatchunk} tar')
    if storage_type == "s3":
        tar_name = f'{jcatchunk}_forcings.tar.gz'
        buffer = BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as jtar:
            for j, jcat in enumerate(catchments):
                jbuff = tar_buffs[j]
                jfilename = filenames[j]
                info = tarfile.TarInfo(name=jfilename)
                info.size = len(jbuff.getbuffer())
                jtar.addfile(info, jbuff) 

        print(f'Uploading {jcatchunk} tar to s3')
        buffer.seek(0)
        bucket, key = convert_url2key(forcing_path,storage_type)
        s3 = boto3.client("s3")   
        s3.put_object(Bucket = bucket, Key = key + "/" + tar_name, Body = buffer.getvalue())   
    else:
        tar_name = Path(forcing_path,f'{jcatchunk}_forcings.tar.gz')
        with tarfile.open(tar_name, 'w:gz') as jtar:
            for j, jcat in enumerate(catchments):
                jbuff = tar_buffs[j]
                jfilename = filenames[j]
                info = tarfile.TarInfo(name=jfilename)
                info.size = len(jbuff.getbuffer())
                jtar.addfile(info, jbuff)     

def multiprocess_write_tars(dfs,catchments,filenames,tar_buffs):  
    """
    Write DataFrames to tar archives using multiprocessing.

    Args:
        dfs: List of pandas DataFrames.
        catchments: Dictionary containing catchment chunks.
        filenames: List of filenames corresponding to the DataFrames.

    Returns:
        None
    """
    i=0
    k=0
    tar_buffs_list = []
    jcatchunk_list = []
    catchments_list = []
    filenames_list = []
    for j, jchunk in enumerate(catchments):  
        ncatchments = len(catchments[jchunk])
        k += ncatchments
        tar_buffs_list.append(tar_buffs[i:k])
        jcatchunk_list.append(jchunk)
        catchments_list.append(catchments[jchunk])
        filenames_list.append(filenames[i:k]) 
        i=k      

    with cf.ProcessPoolExecutor(max_workers=min(len(catchments),nprocs)) as pool:
        for results in pool.map(
        write_tar,
        tar_buffs_list,
        jcatchunk_list,
        catchments_list,
        filenames_list      
        ):
            pass

def write_netcdf(data, vpu, t_ax, catchments):
    """
    Write 3D array data to a NetCDF file.

    Parameters:
        data (numpy.ndarray): 3D array with dimensions (catchment-id, time, forcing variable).
        vpu (str): Name or identifier of the Variable Processing Unit (VPU).
        t_ax (numpy.ndarray): Array representing time axis.
        catchments (dict.keys()): Keys containing catchment IDs.

    Returns:
        None
    """
    if storage_type == 's3':
        s3_client = boto3.session.Session().client("s3")
        nc_filename = forcing_path + f'/{vpu}_forcings.nc'
    else:
        nc_filename = Path(forcing_path,f'{vpu}_forcings.nc')

    ds = xr.Dataset(
        data_vars={
            "UGRD_10maboveground": (["time", "catchment_id"], data[:, 0, :]),
            "VGRD_10maboveground": (["time", "catchment_id"], data[:, 1, :]),
            "DLWRF_surface": (["time", "catchment_id"], data[:, 2, :]),
            "APCP_surface": (["time", "catchment_id"], data[:, 3, :]),
            "precip_rate": (["time", "catchment_id"], data[:, 4, :]),
            "TMP_2maboveground": (["time", "catchment_id"], data[:, 5, :]),
            "SPFH_2maboveground": (["time", "catchment_id"], data[:, 6, :]),
            "PRES_surface": (["time", "catchment_id"], data[:, 7, :]),
            "DSWRF_surface": (["time", "catchment_id"], data[:, 8, :]),
        },
        coords={
            "time": t_ax,
            "forcing_var": ngen_variables,
            "catchment_id": list(catchments),
        },
    )

    if storage_type == 's3':
        bucket, key = convert_url2key(nc_filename,s3_client)
        with tempfile.NamedTemporaryFile(suffix='.nc') as tmpfile:
            ds.to_netcdf(tmpfile.name, format='NETCDF4')
            tmpfile.seek(0)
            s3_client.upload_file(tmpfile.name, bucket, key)
    else:
        ds.to_netcdf(nc_filename) 

def multiprocess_write_netcdf(data, jcatchment_dict, t_ax):  
    """
    Write DataFrames to tar archives using multiprocessing.

    Parameters:
        data (numpy.ndarray): 3D array with dimensions (catchment-id, time, forcing variable).
        jcatchment_dict (dict): Dictionary containing catchment chunks.
        t_ax (numpy.ndarray): Array representing time axis.

    Returns:
        None
    """    
    i=0
    k=0
    data_list = []
    vpu_list = []
    t_ax_list = []
    catchments_list = []
    for j, jchunk in enumerate(jcatchment_dict):  
        ncatchments = len(jcatchment_dict[jchunk])
        k += ncatchments
        data_list.append(data[:,:,i:k])
        vpu_list.append(jchunk)
        t_ax_list.append(t_ax)
        catchments_list.append(jcatchment_dict[jchunk]) 
        i=k      

    with cf.ProcessPoolExecutor(max_workers=min(len(jcatchment_dict),nprocs)) as pool:
        pool.map(write_netcdf,data_list, vpu_list, t_ax_list,catchments_list)

def prep_ngen_data(conf):
    """
    Primary function to retrieve forcing data and convert it into files that can be ingested into ngen.

    Inputs: forcingprocessor config file https://github.com/CIROH-UA/ngen-datastream/blob/main/forcingprocessor/configs/conf.json

    Outputs: ngen forcing files of file type csv, parquet, netcdf, or gzippped tar

    Docs: https://github.com/CIROH-UA/ngen-datastream/blob/main/forcingprocessor/README.md
    """

    t_start = time.perf_counter()

    datentime = datetime.utcnow().strftime("%m%d%y_%H%M%S")   

    log_file = "./profile_fp.txt"   
    log_time("FORCINGPROCESSOR_START", log_file) 
    log_time("CONFIGURATION_START", log_file) 

    gpkg_file = conf['forcing'].get("gpkg_file",None)
    nwm_file = conf['forcing'].get("nwm_file","")

    global output_path, output_file_type
    output_path = conf["storage"].get("output_path","")
    output_file_type = conf["storage"].get("output_file_type","csv") 

    global ii_verbose, nprocs
    ii_verbose = conf["run"].get("verbose",False) 
    ii_collect_stats = conf["run"].get("collect_stats",True)
    nprocs = conf["run"].get("nprocs",int(os.cpu_count() * 0.5))
    nfile_chunk = conf["run"].get("nfile_chunk",100000)

    if ii_verbose:
        msg = f"\nForcingProcessor has awoken. Let's do this."
        for x in msg:
            print(x, end='')
            sys.stdout.flush()
            time.sleep(0.05)
        print('\n')
    
    t_extract  = 0
    write_time = 0

    file_types = ["csv", "parquet","tar","netcdf"]
    for jtype in output_file_type:
        assert (
            jtype in file_types
        ), f"{jtype} for output_file_type is not accepted! Accepted: {file_types}"
    global storage_type
    if "s3" in output_path:
        storage_type = "s3"
    elif "google" in output_path:
        storage_type = "google"
    else:
        storage_type = "local"
    
    global forcing_path
    if storage_type == "local":
        if output_path == "":
            output_path = os.path.join(os.getcwd(),datentime)        
        output_path  = Path(output_path)
        forcing_path = Path(output_path, 'forcings')  
        meta_path    = Path(output_path, 'metadata') 
        metaf_path   = Path(output_path, 'metadata','forcings_metadata')        
        if not os.path.exists(output_path):  os.system(f"mkdir {output_path}")
        if not os.path.exists(forcing_path): os.system(f"mkdir {forcing_path}")
        if not os.path.exists(meta_path):    os.system(f"mkdir {meta_path}")
        if not os.path.exists(metaf_path):   os.system(f"mkdir {metaf_path}")
        conf_path = Path
        with open(f"{metaf_path}/conf.json", 'w') as f:
            json.dump(conf, f)

    elif storage_type == "s3":
        bucket_path  = output_path
        forcing_path = bucket_path + '/forcings'
        meta_path    = bucket_path + '/metadata'
        metaf_path   = bucket_path + '/metadata/forcings_metadata'
        bucket, key  = convert_url2key(metaf_path,storage_type)
        conf_path    = f"{key}/conf_fp.json"
        s3 = boto3.client("s3")          
        s3.put_object(
                Body=json.dumps(conf),
                Bucket=bucket,
                Key=conf_path
            )

    log_time("CONFIGURATION_END", log_file) 
    log_time("READWEIGHTS_START", log_file) 
    if ii_verbose: print(f'Opening weight file...\n',flush=True) 
    if type(gpkg_file) is not list: gpkg_files = [gpkg_file]
    else: gpkg_files = gpkg_file
    global weights_json
    weights_json = {}
    jcatchment_dict = {}
    count = 0
    for jgpkg in gpkg_files:
        ii_json = jgpkg.split('.')[-1] == "json"
        ii_weights_in_bucket = jgpkg.find('//') >= 0
        pattern = r'VPU_([^/]+)'
        match = re.search(pattern, jgpkg)
        if match: jname = "VPU_" + match.group(1)
        else:
            count +=1
            jname = str(count)
        if ii_weights_in_bucket:
            s3 = boto3.client("s3")    
            jgpkg_bucket = jgpkg.split('/')[2]
            ii_uri = jgpkg.find('s3://') >= 0
            if ii_uri:
                jgpkg_key = jgpkg[jgpkg.find(jgpkg_bucket)+len(jgpkg_bucket)+1:]
            else:
                jgpkg_bucket = jgpkg_bucket.split('.')[0]
                jgpkg_key    = jgpkg.split('amazonaws.com/')[-1]
            jobj = s3.get_object(Bucket=jgpkg_bucket, Key=jgpkg_key)
            if ii_json: 
                new_dict = json.loads(jobj["Body"].read().decode())
            else:
                new_dict = hydrofabric2datastream_weights(jobj["Body"].read().decode())
        else:     
            if ii_json:
                with open(jgpkg, "r") as f:
                    new_dict = json.load(f)
            else:
                new_dict = hydrofabric2datastream_weights(jgpkg)
        weights_json = weights_json | new_dict
        jcatchment_dict[jname] = list(weights_json.keys())
    ncatchments = len(weights_json)
    log_time("READWEIGHTS_END", log_file)  

    x_min_list = []
    x_max_list = []
    y_min_list = []
    y_max_list = []
    idx_2d = []
    for jcat in weights_json:
        indices = weights_json[jcat][0]
        if len(indices) == 0: raise Exception(f"No weights found for catchment {jcat}")
        idx_2d=np.unravel_index(indices, (1, 4608, 3840), order='F')
        x_min_list.append(np.min(idx_2d[1]))
        x_max_list.append(np.max(idx_2d[1]))
        y_min_list.append(np.min(idx_2d[2]))
        y_max_list.append(np.max(idx_2d[2]))   
    global x_min, x_max, y_min, y_max
    x_min=np.min(x_min_list)   
    x_max=np.max(x_max_list)   
    y_min=np.min(y_min_list)   
    y_max=np.max(y_max_list)   

    nwm_forcing_files = []
    with open(nwm_file,'r') as fp:
        for jline in fp.readlines():
            nwm_forcing_files.append(jline.strip())
    nfiles = len(nwm_forcing_files)

    global fs_type
    if 's3://' in nwm_forcing_files[0] or 's3.amazonaws' in nwm_forcing_files[0]:
        fs = s3fs.S3FileSystem(
            anon=True,
            client_kwargs={'region_name': 'us-east-1'}
            )
        fs_type = 's3'
    elif 'google' in nwm_forcing_files[0] or 'gs://' in nwm_forcing_files[0] or 'gcs://' in nwm_forcing_files[0]:
        fs = "google"
        fs_type = 'google'
    else:
        fs = None
        fs_type = None

    if ii_verbose:
        print(f"NWM file names:")
        for jfile in nwm_forcing_files:
            print(f"{jfile}")

    if ii_verbose: print(f'Entering primary cycle\n',flush=True)
    nfiles_tot = min(nfile_chunk,nfiles)
    if ii_verbose: print(f'Time loop chunk number: {nfiles_tot}\n',flush=True)
    nloops      = int(np.ceil(nfiles / nfile_chunk))
    ii_append = False
    for jloop in range(nloops):
        log_time("PROCESSING_START", log_file)
        t00 = time.perf_counter()
        start = jloop*nfile_chunk
        end   = min(start + nfile_chunk,nfiles)
        jnwm_files = nwm_forcing_files[start:end]
        t0 = time.perf_counter()
        if ii_verbose: print(f'Entering data extraction...\n',flush=True)        
        data_array, t_ax = multiprocess_data_extract(jnwm_files,nprocs,weights_json,fs)
        t_extract = time.perf_counter() - t0
        complexity = (nfiles_tot * ncatchments) / 10000
        score = complexity / t_extract
        if ii_verbose: print(f'Data extract processs: {nprocs:.2f}\nExtract time: {t_extract:.2f}\nComplexity: {complexity:.2f}\nScore: {score:.2f}\n', end=None,flush=True)
        log_time("PROCESSING_END", log_file)

        log_time("FILEWRITING_START", log_file)
        t0 = time.perf_counter()
        if "netcdf" in output_file_type:
            multiprocess_write_netcdf(data_array, jcatchment_dict, t_ax)
        if ii_verbose: print(f'Writing catchment forcings to {output_path}!', end=None,flush=True)  
        forcing_cat_ids, dfs, filenames, file_sizes, file_sizes_zipped, tar_buffs = multiprocess_write(data_array,t_ax,weights_json.keys(),nprocs,forcing_path,ii_append)

        ii_append = True
        write_time += time.perf_counter() - t0    
        write_rate = ncatchments / write_time
        if ii_verbose: print(f'\n\nWrite processs: {nprocs}\nWrite time: {write_time:.2f}\nWrite rate {write_rate:.2f} files/second\n', end=None,flush=True)
        loop_time = time.perf_counter() - t00
        if ii_verbose and nloops > 1: print(f'One loop took {loop_time:.2f} seconds. Estimated time to completion: {loop_time * (nloops - jloop):.2f}',flush=True)
        log_time("FILEWRITING_END", log_file)

    runtime = time.perf_counter() - t_start
    
    # Metadata        
    if ii_collect_stats:
        log_time("METADATA_START", log_file)
        t000 = time.perf_counter()
        if ii_verbose: print(f'Data processing, now collecting metadata...',flush=True)

        nwm_file_sizes = []
        for j, jfile in enumerate(nwm_forcing_files):
            if j > 10: break
            if fs:
                if jfile.find('https://') >= 0: _, bucket_key  = convert_url2key(jfile, fs_type) 
                else: bucket_key = jfile
                if fs_type == 'google': fs = gcsfs.GCSFileSystem() 
                
                response = fs.open(bucket_key, mode='rb')
                nwm_file_sizes.append(response.details['size'])
            elif jfile.find('https://') >= 0:
                nwm_file_sizes = len(requests.get(jfile).content)
            else:
                nwm_file_sizes = os.path.getsize(jfile)                            

        nwm_file_size_avg = np.average(nwm_file_sizes)
        nwm_file_size_med = np.median(nwm_file_sizes)
        nwm_file_size_std = np.std(nwm_file_sizes)

        catch_file_size_avg = np.average(np.fromiter(file_sizes, dtype=float))
        catch_file_size_med = np.median(file_sizes)
        catch_file_size_std = np.std(file_sizes)    

        catch_file_zip_size_avg = np.average(file_sizes_zipped)
        catch_file_zip_size_med = np.median(file_sizes_zipped)
        catch_file_zip_size_std = np.std(file_sizes_zipped)  

        mil = 1000000

        metadata = {        
            "runtime_s"               : [round(runtime,2)],
            "nvars_intput"            : [len(nwm_variables)],               
            "nwmfiles_input"          : [len(nwm_forcing_files)],           
            "nwm_file_size_avg_MB"    : [nwm_file_size_avg/mil],
            "nwm_file_size_med_MB"    : [nwm_file_size_med/mil],
            "nwm_file_size_std_MB"    : [nwm_file_size_std/mil],
            "catch_files_output"      : [nfiles],
            "nvars_output"            : [len(ngen_variables)],
            "catch_file_size_avg_MB"  : [catch_file_size_avg/mil],
            "catch_file_size_med_MB"  : [catch_file_size_med/mil],
            "catch_file_size_std_MB"  : [catch_file_size_std/mil],
            "catch_file_zip_size_avg_MB" : [catch_file_zip_size_avg/mil],
            "catch_file_zip_size_med_MB" : [catch_file_zip_size_med/mil],
            "catch_file_zip_size_std_MB" : [catch_file_zip_size_std/mil],                                                 
        }

        data_avg = np.average(data_array,axis=0)
        avg_df = pd.DataFrame(data_avg.T,columns=ngen_variables)
        avg_df.insert(0,"catchment id",forcing_cat_ids)

        data_med = np.median(data_array,axis=0)
        med_df = pd.DataFrame(data_med.T,columns=ngen_variables)
        med_df.insert(0,"catchment id",forcing_cat_ids)     

        del data_array   

        metadata_df = pd.DataFrame.from_dict(metadata)
        if storage_type == 's3':
            bucket, key = convert_url2key(output_path,storage_type)
            
            meta_path = f"{key}/metadata/forcings_metadata/"
            buf = BytesIO()   
            if "parquet" in output_file_type: 
                filename = f"metadata.parquet"
                metadata_df.to_parquet(buf, index=False)
            else: 
                filename = f"metadata.csv"
                metadata_df.to_csv(buf, index=False)
            buf.seek(0)
            key_name = meta_path + filename
            s3.put_object(Bucket=bucket, Key=key_name, Body=buf.getvalue())
            if "parquet" in output_file_type: 
                filename = f"catchments_avg.parquet"
                avg_df.to_parquet(buf, index=False)
            else: 
                filename = f"catchments_avg.csv"
                avg_df.to_csv(buf, index=False)
            buf.seek(0)
            key_name = meta_path + filename
            s3.put_object(Bucket=bucket, Key=key_name, Body=buf.getvalue())                    
            if "parquet" in output_file_type:  
                filename = f"catchments_median.parquet"
                med_df.to_parquet(buf, index=False)
            else: 
                filename = f"catchments_median.csv"
                med_df.to_csv(buf, index=False)
            buf.seek(0)
            key_name = meta_path + filename
            s3.put_object(Bucket=bucket, Key=key_name, Body=buf.getvalue())
            buf.close()
        else:
            if "parquet" in output_file_type:
                filename = Path(metaf_path, f"metadata.parquet")
                metadata_df.to_parquet(filename, index=False)
            else: 
                filename = Path(metaf_path, f"metadata.csv")
                metadata_df.to_csv(filename, index=False)
            if "parquet" in output_file_type:
                filename = Path(metaf_path, f"catchments_avg.parquet")
                avg_df.to_parquet(filename, index=False)
            else: 
                filename = Path(metaf_path, f"catchments_avg.csv")
                avg_df.to_csv(filename, index=False)
            if "parquet" in output_file_type:
                filename = Path(metaf_path, f"catchments_median.parquet")
                med_df.to_parquet(filename, index=False)
            else: 
                filename = Path(metaf_path, f"catchments_median.csv")
                med_df.to_csv(filename, index=False)
        meta_time = time.perf_counter() - t000
        log_time("METADATA_END", log_file)

    if "tar" in output_file_type:
        log_time("TAR_START", log_file)
        if ii_verbose: print(f'\nWriting tarball...',flush=True)
        t0000 = time.perf_counter()
        multiprocess_write_tars(dfs,jcatchment_dict,filenames,tar_buffs)    
        tar_time = time.perf_counter() - t0000
        log_time("TAR_END", log_file)

    if storage_type == "s3": 
        bucket, key  = convert_url2key(metaf_path,storage_type)
        log_path = key + '/log_fp.txt'
        s3.upload_file(
                f'./log_fp.txt',
                bucket,
                log_path
            )

    if ii_verbose:
        print(f"\n\n--------SUMMARY-------")
        msg = f"\nData has been written to {output_path}"
        msg += f"\nProcess data  : {t_extract:.2f}s"
        msg += f"\nWrite data    : {write_time:.2f}s"
        if ii_collect_stats: 
            runtime += meta_time
            msg += f"\nCollect stats : {meta_time:.2f}s"
        if "tar" in output_file_type:
            runtime += tar_time
            msg += f"\nWrite tar     : {tar_time:.2f}s"
        msg += f"\nRuntime       : {runtime:.2f}s\n"
        print(msg)
    log_time("FORCINGPROCESSOR_END", log_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        dest="infile", type=str, help="A json containing user inputs to run forcingprocessor"
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

    prep_ngen_data(conf)




