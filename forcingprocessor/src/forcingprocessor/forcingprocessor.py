import pandas as pd
import argparse, os, json, sys
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
from datetime import datetime
import psutil
import gzip
import tarfile, tempfile

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

    return bucket_key

def distribute_work(items,nprocs):
    """
    Distribute items evenly between processes, round robin
    """
    items_per_proc = [0 for x in range(nprocs)]
    for j in range(len(items)):
        k = j % nprocs
        items_per_proc[k] = items_per_proc[k] + 1
    assert len(items) == np.sum(items_per_proc)
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

    completion_time = [single_ex * x / exec_count + 2*j for j, x in enumerate(items_per_proc)]
    global ntasked
    ntasked = len(np.nonzero(items_per_proc)[0])
    if nprocs > ntasked: 
        if ii_verbose: print(f'Not enough work for {nprocs} requested processes, downsizing to {ntasked}')
        nprocs = ntasked
        completion_time = completion_time[:ntasked]
        items_per_proc = items_per_proc[:ntasked]
    if ii_verbose: print(f'item distribution {items_per_proc}')
    if ii_verbose: print(f'Expected completion time {max(completion_time)} s with {nprocs} processes')

    assert nitems == np.sum(items_per_proc)
    return items_per_proc

def report_usage():
    usage_ram   = psutil.virtual_memory()[3]/1000000000
    percent_ram = psutil.virtual_memory()[2]
    percent_cpu = psutil.cpu_percent()
    if ii_verbose: print(f'\nCurrent RAM usage (GB): {usage_ram:.2f}, {percent_ram:.2f}%\nCurrent CPU usage : {percent_cpu:.2f}%')
    return

def multiprocess_data_extract(files,nprocs,crosswalk_dict,fs):
    """
    Sets up the multiprocessing pool for forcing_grid2catchment and returns the data and time axis ordered in time
    
    """
    launch_time     = 0.05
    cycle_time      = 35
    files_per_cycle = 1
    files_per_proc  = distribute_work(files,nprocs)
    files_per_proc  = load_balance(files_per_proc,launch_time,cycle_time,files_per_cycle)
    nprocs          = len(files_per_proc)

    start  = 0
    nfiles = len(files)
    files_list          = []
    fs_list             = []
    for i in range(nprocs):
        end = min(start + files_per_proc[i],nfiles)
        files_list.append(files[start:end])
        fs_list.append(fs)
        start = end

    def init_pool(the_data):
        global weights_json
        weights_json = the_data        

    data_ax = []
    t_ax_local = []
    with cf.ProcessPoolExecutor(max_workers=nprocs, initializer=init_pool, initargs=(crosswalk_dict,)) as pool:
        for results in pool.map(
        forcing_grid2catchment,
        files_list,
        fs_list
        ):
            data_ax.append(results[0])
            t_ax_local.append(results[1])

    gigs = nfiles * len(crosswalk_dict) * len(nwm_variables) * 4 / 1000000000
    if ii_verbose: print(f'Building data array - > {gigs:.2f} GB')
    data_array = np.concatenate(data_ax)
    del data_ax
    t_ax_local = [item for sublist in t_ax_local for item in sublist]
  
    return data_array, t_ax_local

def forcing_grid2catchment(nwm_files: list, fs=None):
    """
    General function to retrieve catchment level data from national water model files

    Inputs:
    nwm_files: list of filenames (urls for remote, local paths otherwise),
    fs: an optional file system for cloud storage reads

    Outputs:
    df_by_t : (returned for local files) a list (in time) of forcing data. Note that this list may not be consistent in time
    t : model_output_valid_time for each

    """
    topen = 0
    txrds = 0
    tfill = 0    
    tdata = 0    
    data_list = []
    t_list = []
    nfiles = len(nwm_files)
    nvar = len(nwm_variables)
    if fs_type == 'google' : fs = gcsfs.GCSFileSystem() 
    id = os.getpid()
    if ii_verbose: print(f'Process #{id} extracting data from {nfiles} files',end=None,flush=True)
    for j, nwm_file in enumerate(nwm_files):
        t0 = time.perf_counter()        
        eng    = "h5netcdf"
        if fs:
            if nwm_file.find('https://') >= 0: bucket_key = convert_url2key(nwm_file,fs_type)
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
            data_allvars = np.zeros(shape=(nvar, shp[1], shp[2]), dtype=np.float32)            
            for var_dx, jvar in enumerate(nwm_variables):                
                if jvar == 'RAINRATE': # HACK CONVERSION
                    data_allvars[var_dx, :, :] = 3600 * np.squeeze(nwm_data[jvar].values)
                else:
                    data_allvars[var_dx, :, :] = np.squeeze(nwm_data[jvar].values)   

            time_splt = nwm_data.attrs["model_output_valid_time"].split("_")
            t = time_splt[0] + " " + time_splt[1]
            t_list.append(t)       
        del nwm_data
        tfill += time.perf_counter() - t0        

        t0 = time.perf_counter()
        data_allvars = data_allvars.reshape(nvar, shp[1] * shp[2])
        ncatch = len(weights_json)
        data_array = np.zeros((nvar,ncatch), dtype=np.float32)
        jcatch = 0
        for key, value in weights_json.items(): 
            weights = value[0]
            coverage = np.array(value[1])
            coverage_mat = np.repeat(coverage[None,:],nvar,axis=0)
            jcatch_data_mask = data_allvars[:,weights] 
            weight_sum = np.sum(coverage)
            data_array[:,jcatch] = np.sum(coverage_mat * jcatch_data_mask ,axis=1) / weight_sum  

            jcatch += 1  
        data_list.append(data_array)
        tdata += time.perf_counter() - t0
        ttotal = topen + txrds + tfill + tdata
        if ii_verbose: print(f'\nAverage time for:\nfs open file: {topen/(j+1):.2f} s\nxarray open dataset: {txrds/(j+1):.2f} s\nfill array: {tfill/(j+1):.2f} s\ncalculate catchment values: {tdata/(j+1):.2f} s\ntotal {ttotal/(j+1):.2f} s', end=None,flush=True)
        report_usage()

    if ii_verbose: print(f'Process #{id} completed data extraction, returning data to primary process')
    return [data_list, t_list]

def multiprocess_write(data,t_ax,catchments,nprocs,output_bucket,out_path,ii_append):
    """
    Sets up the process pool for write_data
    
    """

    launch_time          = 0.05
    cycle_time           = 1
    catchments_per_cycle = 223
    catchments_per_proc  = distribute_work(catchments,nprocs)
    catchments_per_proc  = load_balance(catchments_per_proc,launch_time,cycle_time,catchments_per_cycle)

    ntasked = len(np.nonzero(catchments_per_proc)[0])
    if nprocs > ntasked: 
        if ii_verbose: print(f'Not enough work for {nprocs} requested processes, downsizing to {ntasked}')
    
    ncatchments           = len(catchments)
    out_path_list         = []
    append_list           = []
    print_list            = []
    bucket_list           = []
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
            bucket_list.append(output_bucket)

            worker_catchments = {}
            count = 0
            
            i += 1

    ids = []
    dfs = []
    filenames = []
    with cf.ProcessPoolExecutor(max_workers=nprocs) as pool:
         for results in pool.map(
        write_data,
        worker_data_list,
        worker_time_list,
        worker_catchment_list,
        bucket_list,
        out_path_list,
        append_list,  
        print_list,      
        ):
            ids.append(results[0])
            dfs.append(results[1])
            filenames.append(results[2])

    print(f'\n\nGathering data from write processes...')

    if len(ids) > 1:
        flat_ids  = [item for sublist in ids for item in sublist]
        flat_dfs  = [item for sublist in dfs for item in sublist]
        flat_filenames = [item for sublist in filenames for item in sublist]
    else:
        flat_ids  = ids
        flat_dfs = dfs
        flat_filenames = filenames

    return flat_ids, flat_dfs, flat_filenames

def write_data(
        data,
        t_ax,
        catchments,
        bucket,
        out_path,
        ii_append,
        ii_print
                
):
    s3_client = boto3.session.Session().client("s3")   

    nfiles = len(catchments)
    id = os.getpid()
    if ii_verbose: print(f'{id} writing {nfiles} dataframes to {output_file_type}', end=None)

    forcing_cat_ids = []
    dfs = []
    filenames = []
    write_int = 400
    t_df      = 0
    t_buff    = 0
    t_put     = 0

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
        
        if ii_append:
            key = (out_path/f"cat-{cat_id}.csv").resolve()
            df_bucket = pd.read_csv(s3_client.get_object(Bucket = bucket, Key = key).get("Body"))
            df = pd.concat([df_bucket,df])
            del df_bucket              

        if storage_type.lower() == 's3':
            buf = BytesIO()
            filename = f"cat-{cat_id}." + output_file_type

            dfs.append(df)
            filenames.append(str(Path(filename).name))  

            if output_file_type == "parquet":
                df.to_parquet(buf, index=False)                
            elif output_file_type == "csv":
                df.to_csv(buf, index=False)                 

            t_buff += time.perf_counter() - t0
            t0 = time.perf_counter()

            buf.seek(0)            
            s3_client.put_object(Bucket=bucket, Key=out_path + filename, Body=buf.getvalue()) 
            t_put += time.perf_counter() - t0            

        elif storage_type == 'local':
            filename = str((out_path/Path(f"cat-{cat_id}." + output_file_type)).resolve())
            if output_file_type == "parquet":
                df.to_parquet(filename, index=False)                
            elif output_file_type == "csv":
                df.to_csv(filename, index=False)                                         

        if j == 0:
            if storage_type.lower() == 's3':
                key = out_path + filename
                file_size_MB = s3_client.get_object(Bucket = bucket, Key = key).get('ContentLength') / 1000000
            else:
                file_size_MB = os.path.getsize(filename) / 1000000

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
                if storage_type.lower() == "s3": msg += f"buff             {t_buff:.2f}s\n"
                if storage_type.lower() == "s3": msg += f"put              {t_put:.2f}s\n"                
                msg += f"estimated total write time {estimate_total_time:.2f}s\n"
                msg += f"progress                   {(j+1)/nfiles*100:.2f}%\n"
                msg += f"Bandwidth (all processs)   {bandwidth_Mbps:.2f} Mbps"
                print(msg)

    return forcing_cat_ids, dfs, filenames

def start_end_interval(start_date,end_date,lead_time):
    start_obj = datetime.strptime(start_date, "%Y%m%d%H%M")
    end_obj   = datetime.strptime(end_date, "%Y%m%d%H%M")

    formatted_start = start_obj.strftime("%Y-%m-%d %H:%M:%S")
    formatted_end   = end_obj.strftime("%Y-%m-%d %H:%M:%S")

    if len(lead_time) > 1: output_interval = (lead_time[1] - lead_time[0]) * 3600
    else: output_interval = 3600

    return formatted_start, formatted_end, output_interval

def prep_ngen_data(conf):
    """
    Primary function to retrieve forcing and hydrofabric data and convert it into files that can be ingested into ngen.

    Inputs: <arg1> JSON config file specifying start_date, end_date, and vpu

    Outputs: ngen forcing files

    Will store files in the same folder as the JSON config to run this script
    """

    t_start = time.perf_counter()

    datentime = datetime.utcnow().strftime("%m%d%y_%H%M%S")       

    start_date = conf["forcing"].get("start_date",None)
    end_date = conf["forcing"].get("end_date",None)
    weight_file = conf['forcing'].get("weight_file",None)
    nwm_file = conf['forcing'].get("nwm_file","")

    start_time, end_time, output_interval = start_end_interval(start_date,end_date,[])
    conf['time']                    = {}
    conf['time']['start_time']      = start_time
    conf['time']['end_time']        = end_time
    conf['time']['output_interval'] = output_interval

    global storage_type, output_file_type
    storage_type = conf["storage"]["storage_type"]
    output_bucket = conf["storage"].get("output_bucket","")
    output_path = conf["storage"].get("output_path","")
    output_file_type = conf["storage"].get("output_file_type","csv") 

    global ii_verbose
    ii_verbose = conf["run"].get("verbose",False) 
    ii_collect_stats = conf["run"].get("collect_stats",True)
    ii_tar = conf["run"].get("ii_tar",True)
    proc_process = conf["run"].get("proc_process",None)
    write_process = conf["run"].get("write_process",None)
    nfile_chunk = conf["run"].get("nfile_chunk",None)

    if proc_process is None: proc_process   = int(os.cpu_count() * 0.5)
    if write_process is None: write_process = os.cpu_count()
    if nfile_chunk is None: nfile_chunk     = 100000

    if ii_verbose:
        msg = f"\nForcingProcessor has awoken. Let's do this."
        for x in msg:
            print(x, end='')
            sys.stdout.flush()
            time.sleep(0.05)
        print('\n')
    
    t_extract  = 0
    write_time = 0

    # configuration validation
    file_types = ["csv", "parquet"]
    assert (
        output_file_type in file_types
    ), f"{output_file_type} for output_file_type is not accepted! Accepted: {file_types}"
    bucket_types = ["local", "s3"]
    assert (
        storage_type.lower() in bucket_types
    ), f"{storage_type} for storage_type is not accepted! Accepted: {bucket_types}"

    if storage_type == "local":

        if output_path == "":
            output_path = os.path.join(os.getcwd(),datentime)        

        # Prep output directory
        bucket_path  = Path(output_path, output_bucket)
        forcing_path = Path(bucket_path, 'forcings')  
        meta_path    = Path(bucket_path, 'metadata') 
        metaf_path   = Path(bucket_path, 'metadata','forcings_metadata')        
        if not os.path.exists(bucket_path):  os.system(f"mkdir {bucket_path}")
        if not os.path.exists(forcing_path): os.system(f"mkdir {forcing_path}")
        if not os.path.exists(meta_path):    os.system(f"mkdir {meta_path}")
        if not os.path.exists(metaf_path):   os.system(f"mkdir {metaf_path}")
        output_path = bucket_path

        with open(f"{bucket_path}/metadata/forcings_metadata/conf.json", 'w') as f:
            json.dump(conf, f)

    elif storage_type == "S3":

        s3 = boto3.client("s3")          
    
        s3.put_object(
                Body=json.dumps(conf),
                Bucket=output_bucket,
                Key=f"{output_path}/metadata/forcings_metadata/conf.json"
            )

    if ii_verbose: print(f'Opening weight file...\n')        
    ii_weights_in_bucket = weight_file.find('//') >= 0
    if ii_weights_in_bucket:
        s3 = boto3.client("s3")    
        weight_file_bucket = weight_file.split('/')[2]
        ii_uri = weight_file.find('s3://') >= 0
        
        if ii_uri:
            weight_file_key = weight_file[weight_file.find(weight_file_bucket)+len(weight_file_bucket)+1:]
        else:
            weight_file_bucket = weight_file_bucket.split('.')[0]
            weight_file_key    = weight_file.split('amazonaws.com/')[-1]
                
        weight_file_obj = s3.get_object(Bucket=weight_file_bucket, Key=weight_file_key)    
        crosswalk_dict = json.loads(weight_file_obj["Body"].read().decode())
    else:
        with open(weight_file, "r") as f:
            crosswalk_dict = json.load(f)

    ncatchments = len(crosswalk_dict)

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

    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.tar.gz') and file.find('tmp_') == 0:
                tar_path = os.path.join(root, file)
                os.remove(tar_path)

    if ii_verbose: print(f'Entering primary cycle\n')
    nfiles_tot = min(nfile_chunk,nfiles)
    if ii_verbose: print(f'Time loop chunk number: {nfiles_tot}\n')
    nloops      = int(np.ceil(nfiles / nfile_chunk))
    ii_append = False
    for jloop in range(nloops):

        t00 = time.perf_counter()
        start = jloop*nfile_chunk
        end   = min(start + nfile_chunk,nfiles)
        jnwm_files = nwm_forcing_files[start:end]
        t0 = time.perf_counter()
        if ii_verbose: print(f'Entering data extraction...\n')
        # [data_array, t_ax] = forcing_grid2catchment(crosswalk_dict, jnwm_files, fs)
        data_array, t_ax = multiprocess_data_extract(jnwm_files,proc_process,crosswalk_dict,fs)
        t_extract = time.perf_counter() - t0
        complexity = (nfiles_tot * ncatchments) / 10000
        score = complexity / t_extract
        if ii_verbose: print(f'Data extract processs: {proc_process:.2f}\nExtract time: {t_extract:.2f}\nComplexity: {complexity:.2f}\nScore: {score:.2f}\n', end=None)

        t0 = time.perf_counter()
        out_path = (output_path/'forcings/').resolve()
        if ii_verbose: print(f'Writing catchment forcings to {output_bucket} at {out_path}!', end=None)  
        forcing_cat_ids, dfs, filenames = multiprocess_write(data_array,t_ax,crosswalk_dict.keys(),write_process,output_bucket,out_path,ii_append)      


        ii_append = True
        write_time += time.perf_counter() - t0    
        write_rate = ncatchments / write_time
        if ii_verbose: print(f'\n\nWrite processs: {write_process}\nWrite time: {write_time:.2f}\nWrite rate {write_rate:.2f} files/second\n', end=None)

        loop_time = time.perf_counter() - t00
        if ii_verbose and nloops > 1: print(f'One loop took {loop_time:.2f} seconds. Estimated time to completion: {loop_time * (nloops - jloop):.2f}')

    runtime = time.perf_counter() - t_start

    # Metadata        
    if ii_collect_stats:
        t000 = time.perf_counter()
        if ii_verbose: print(f'Data processing and writing is complete, now collecting metadata...')

        # Write out a csv with script runtime stats
        nwm_file_sizes = []
        for j, jfile in enumerate(nwm_forcing_files):
            if j > 10: break
            if fs:
                if jfile.find('https://') >= 0: bucket_key  = convert_url2key(jfile, fs_type) 
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

        catchment_sizes = []
        zipped_sizes = []
        for j, jcatch in enumerate(forcing_cat_ids):   
            # Check forcing size
            if j > 10: break
            filename = str(output_path) + "/forcings/" + f"cat-{jcatch}." + output_file_type
            if storage_type.lower() == 's3':                
                response = s3.head_object(
                    Bucket=output_bucket,
                    Key=filename
                    )
                size = response['ContentLength']
            else:
                size = os.path.getsize(filename)
            
            catchment_sizes.append(size)

            # get zipped size            
            zipname  = f"cat-{jcatch}." + 'zip'
            zip_dir = f"{str(output_path)}/metadata/forcings_metadata/zipped_forcing/"
            key_name = zip_dir + zipname
            if storage_type.lower() == 's3':  
                buf = BytesIO()
                buf.seek(0)
                df = pd.DataFrame(data_array[:,:,j])
                with gzip.GzipFile(mode='w', fileobj=buf) as zipped_file:
                    df.to_csv(TextIOWrapper(zipped_file, 'utf8'), index=False)                
                s3.put_object(Bucket=output_bucket, Key=key_name, Body=buf.getvalue())    
                buf.close()                
                response = s3.head_object(
                    Bucket=output_bucket,
                    Key=key_name
                )
                size = response['ContentLength']
            else:
                if not os.path.exists(zip_dir): os.mkdir(zip_dir)
                df = pd.DataFrame(data_array[:,:,j])
                with gzip.GzipFile(key_name, mode='w') as zipped_file:
                    df.to_csv(TextIOWrapper(zipped_file, 'utf8'), index=False) 
                size = os.path.getsize(key_name)

            zipped_sizes.append(size)

        catch_file_size_avg = np.average(catchment_sizes)
        catch_file_size_med = np.median(catchment_sizes)
        catch_file_size_std = np.std(catchment_sizes)    

        catch_file_zip_size_avg = np.average(zipped_sizes)
        catch_file_zip_size_med = np.median(zipped_sizes)
        catch_file_zip_size_std = np.std(zipped_sizes)  

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

        # Save input config file and script commit 
        metadata_df = pd.DataFrame.from_dict(metadata)
        if storage_type == 'S3':
            
            # Write files to s3 bucket
            meta_path = f"{str(output_path)}/metadata/forcings_metadata/"
            buf = BytesIO()   
            filename = f"metadata." + output_file_type
            if output_file_type == "csv": metadata_df.to_csv(buf, index=False)
            else: metadata_df.to_parquet(buf, index=False)
            buf.seek(0)
            key_name = meta_path + filename
            s3.put_object(Bucket=output_bucket, Key=key_name, Body=buf.getvalue())
            filename = f"catchments_avg." + output_file_type
            if output_file_type == "csv": avg_df.to_csv(buf, index=False)
            else: avg_df.to_parquet(buf, index=False)
            buf.seek(0)
            key_name = meta_path + filename
            s3.put_object(Bucket=output_bucket, Key=key_name, Body=buf.getvalue())        
            filename = f"catchments_median." + output_file_type
            if output_file_type == "csv": med_df.to_csv(buf, index=False)
            else: med_df.to_parquet(buf, index=False)
            buf.seek(0)
            key_name = meta_path + filename
            s3.put_object(Bucket=output_bucket, Key=key_name, Body=buf.getvalue())
            buf.close()
        else:
            # Write files locally
            filename = Path(metaf_path, f"metadata." + output_file_type)
            if output_file_type == "csv": metadata_df.to_csv(filename, index=False)
            else: metadata_df.to_parquet(buf, index=False)
            filename = Path(metaf_path, f"catchments_avg." + output_file_type)
            if output_file_type == "csv": avg_df.to_csv(filename, index=False)
            else: avg_df.to_parquet(buf, index=False)            
            filename = Path(metaf_path, f"catchments_median." + output_file_type)
            if output_file_type == "csv": med_df.to_csv(filename, index=False)
            else: med_df.to_parquet(buf, index=False)            
        
        meta_time = time.perf_counter() - t000

    if ii_tar:
        if ii_verbose: print(f'\nWriting tarball...')
        t0000 = time.perf_counter()
        if storage_type.lower() == 's3':
            path = "/metadata/forcings_metadata/"
            combined_tar_filename = 'forcings.tar.gz'
            with tarfile.open(combined_tar_filename, 'w:gz') as combined_tar:        
                if ii_collect_stats:
                    buf = BytesIO() 

                    filename = f"metadata." + output_file_type
                    metadata_df.to_csv(buf, index=False)
                    buf.seek(0)
                    tarinfo = tarfile.TarInfo(name=path + filename)
                    tarinfo.size = len(buf.getvalue())
                    combined_tar.addfile(tarinfo, fileobj=buf)    

                    filename = f"catchments_avg." + output_file_type
                    avg_df.to_csv(buf, index=False)
                    buf.seek(0)
                    tarinfo = tarfile.TarInfo(name=path + filename)
                    tarinfo.size = len(buf.getvalue())
                    combined_tar.addfile(tarinfo, fileobj=buf)    

                    filename = f"catchments_median." + output_file_type
                    med_df.to_csv(buf, index=False)
                    buf.seek(0)
                    tarinfo = tarfile.TarInfo(name=path + filename)
                    tarinfo.size = len(buf.getvalue())
                    combined_tar.addfile(tarinfo, fileobj=buf)    
                
                for j, jdf in enumerate(dfs):
                    jfilename = filenames[j]
                    with tempfile.NamedTemporaryFile() as tmpfile:
                        if output_file_type == "parquet":
                            jdf.to_parquet(tmpfile.name, index=False)
                        elif output_file_type == "csv":
                            jdf.to_csv(tmpfile.name, index=False)
                        
                        combined_tar.add(tmpfile.name, arcname=jfilename)
        else:
            path = str(metaf_path)
            combined_tar_filename = str(forcing_path) + '/forcings.tar.gz'
            tar_cmd = f'tar cf - {forcing_path} {metaf_path} | pigz > forcings.tar.gz'
            os.system(tar_cmd)
            os.system(f'mv forcings.tar.gz {combined_tar_filename}')

    tar_time = time.perf_counter() - t0000

    if storage_type == 'S3':
        with open(combined_tar_filename, 'rb') as combined_tar:
            s3 = boto3.client("s3")   
            s3.upload_fileobj(combined_tar,output_bucket,out_path + combined_tar_filename)   
        os.remove(combined_tar_filename)

    if ii_verbose:
        print(f"\n\n--------SUMMARY-------")
        if storage_type == "local": msg = f"\nData has been written locally to {bucket_path}"
        else: msg = f"\nData has been written to S3 bucket {output_bucket} at /{output_path}/forcing"
        msg += f"\nProcess data  : {t_extract:.2f}s"
        msg += f"\nWrite data    : {write_time:.2f}s"
        if ii_collect_stats: 
            runtime += meta_time
            msg += f"\nCollect stats : {meta_time:.2f}s"
        if ii_tar:
            runtime += tar_time
            msg += f"\nWrite tar     : {tar_time:.2f}s"
        msg += f"\nRuntime       : {runtime:.2f}s\n"
        print(msg)

if __name__ == "__main__":
    # Take in user config
    parser = argparse.ArgumentParser()
    parser.add_argument(
        dest="infile", type=str, help="A json containing user inputs to run ngen"
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




