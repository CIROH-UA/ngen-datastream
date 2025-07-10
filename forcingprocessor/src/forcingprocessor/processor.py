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
from datetime import datetime
import gzip
import tarfile, tempfile
from forcingprocessor.weights_hf2ds import multiprocess_hf2ds
from forcingprocessor.plot_forcings import plot_ngen_forcings
from forcingprocessor.utils import get_window, log_time, convert_url2key, report_usage, nwm_variables, ngen_variables

B2MB = 1048576

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

def multiprocess_data_extract(files : list, nprocs : int, weights_df : pd.DataFrame, fs):
    """
    Sets up the multiprocessing pool for forcing_grid2catchment and returns the data and time axis ordered in time.

    Parameters:
        files (list): List of files to be processed.
        nprocs (int): Number of processes to be used.
        weights_df (dict): DataFrame containing catchment weights.
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
    fs_list    = []
    for i in range(nprocs):
        end = min(start + files_per_proc[i],nfiles)
        files_list.append(files[start:end])
        fs_list.append(fs)
        start = end

    data_ax = []
    t_ax_local = []
    nwm_data = []
    nwm_file_sizes = []
    with cf.ProcessPoolExecutor(max_workers=nprocs) as pool:
        for results in pool.map(
        forcing_grid2catchment,
        files_list,
        fs_list
        ):
            data_ax.append(results[0])
            t_ax_local.append(results[1])    
            nwm_data.append(results[2])        
            nwm_file_sizes.append(results[3])        

    print(f'Processes have returned')
    del weights_df
    data_array = np.concatenate(data_ax)
    t_ax_local = [item for sublist in t_ax_local for item in sublist]
    nwm_file_sizes_out = [item for sublist in nwm_file_sizes for item in sublist]
    nwm_data = np.concatenate(nwm_data)
  
    return data_array, t_ax_local, nwm_data, nwm_file_sizes_out

def forcing_grid2catchment(nwm_files: list, fs=None):
    """
    Retrieve catchment level data from national water model files

    Inputs:
    nwm_files: list of filenames (urls for remote, local paths otherwise),
    fs: an optional file system for cloud storage reads

    Outputs: [data_list, t_list, nwm_data]
    data_list : list of ngen forcings ordered in time. ngen_forcings : 2d darray (forcing_variable x catchment)
    t : model_output_valid_time for each
    nwm_data : nwm data saved for plotting. nwm_data : 3d array (forcing_variable x west_east x south_north)

    Globals:
    weights_df : dataframe with catchment-ids as the index and columns indices and coverage
    ngen_variables
    ngen_vars_plot
    ii_plot, nts_plot

    """
    topen = 0
    txrds = 0
    tfill = 0    
    tdata = 0    
    t_list = []
    nwm_data_plot = []
    jplot_vars = np.array([x for x in range(len(ngen_variables)) if ngen_variables[x] in ngen_vars_plot])
    nfiles = len(nwm_files)
    nvar = len(nwm_variables)

    dx = x_max - x_min + 1
    dy = y_max - y_min + 1

    if fs_type == 'google' : fs = gcsfs.GCSFileSystem() 
    id = os.getpid()
    if ii_verbose: print(f'Process #{id} extracting data from {nfiles} files',end=None,flush=True)
    data_list = []
    nwm_file_sizes_MB = []
    for j, nwm_file in enumerate(nwm_files):
        t0 = time.perf_counter()        
        if fs:
            if nwm_file.find('https://') >= 0: _, bucket_key = convert_url2key(nwm_file,fs_type)
            else: bucket_key = nwm_file
            file_obj   = fs.open(bucket_key, mode='rb')
            nwm_file_sizes_MB.append(file_obj.details['size'])
        elif 'https://' in nwm_file:
            response = requests.get(nwm_file)
            
            if response.status_code == 200:
                file_obj = BytesIO(response.content)
            else:
                raise Exception(f"{nwm_file} does not exist")
            nwm_file_sizes_MB.append(len(response.content) / B2MB)
        else:
            file_obj = nwm_file
            nwm_file_sizes_MB = os.path.getsize(nwm_file / B2MB) 

        topen += time.perf_counter() - t0
        t0 = time.perf_counter()  
        with xr.open_dataset(file_obj) as nwm_data:
            txrds += time.perf_counter() - t0
            t0 = time.perf_counter()                     
            shp = nwm_data["U2D"].shape   
            data_allvars = np.zeros(shape=(nvar, dy, dx), dtype=np.float32)       
            for var_dx, jvar in enumerate(nwm_variables):  
                if "retrospective-2-1" in nwm_file:
                    data_allvars[var_dx, :, :] = np.flip(np.squeeze(nwm_data[jvar].isel(west_east=slice(x_min, x_max+1), south_north=slice(shp[1] - (y_max+1), shp[1] - y_min)).values),axis=0)
                    t = datetime.strftime(datetime.strptime(nwm_file.split('/')[-1].split('.')[0],'%Y%m%d%H'),'%Y-%m-%d %H:%M:%S')
                else:                            
                    data_allvars[var_dx, :, :] = np.flip(np.squeeze(nwm_data[jvar].isel(x=slice(x_min, x_max+1), y=slice(shp[1] - (y_max+1), shp[1] - y_min)).values),axis=0)
                    time_splt = nwm_data.attrs["model_output_valid_time"].split("_")
                    t = time_splt[0] + " " + time_splt[1]
            t_list.append(t)       
            if ii_plot and j < nts_plot: nwm_data_plot.append(data_allvars[jplot_vars,:,:])
        del nwm_data
        tfill += time.perf_counter() - t0        

        t0 = time.perf_counter()
        data_allvars = data_allvars.reshape(nvar, dx*dy)
        ncatch = len(weights_df)
        data_array = np.zeros((nvar,ncatch), dtype=np.float32)
        jcatch = 0
        for row in weights_df.itertuples(): 
            weights = row.cell_id
            coverage = np.array(row.coverage)
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
    return [data_list, t_list, nwm_data_plot, nwm_file_sizes_MB]

def multiprocess_write(data,t_ax,catchments,nprocs,out_path):
    """
    Sets up the process pool for write_data.

    Parameters:
        data (numpy.ndarray): 3D array containing the data to be written.
        t_ax (numpy.ndarray): Array representing the time axis of the data.
        catchments (iterable): List of catchment identifiers.
        nprocs (int): Number of processes to be used for writing data.
        out_path (str): Path where the output files will be saved.

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
    forcing_cat_ids = []
    tar_list = []
    dfs = []
    filenames = []
    filename  = ""
    write_int = 400
    t_df      = 0
    bucket = None
    key_prefix = None
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

        if "parquet" in output_file_type or "csv" in output_file_type :
            if "netcdf" in output_file_type: output_file_type.pop(output_file_type.index("netcdf"))
            filename = f"cat-{cat_id}.{output_file_type[0]}"
            if j ==0: 
                if ii_verbose: print(f'{id} writing {nfiles} dataframes to {output_file_type}', end=None, flush =True)
            kwargs = {"s3": s3_client, "bucket": bucket, "key_prefix": key_prefix} if storage_type == "s3" else {"local_path": out_path}
            write_df(df, filename, storage_type, **kwargs)
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
                file_size_MB = os.path.getsize(filename) / B2MB
                os.remove(filename)
            else:
                file_size_MB = os.path.getsize(filename) / B2MB

            pattern = r'\.\w+$'
            filename_zip = re.sub(pattern, '.zip', filename)
            with gzip.GzipFile(filename_zip, mode='w') as zipped_file:
                df.to_csv(TextIOWrapper(zipped_file, 'utf8'), index=False) 
            file_zipped_size_MB = os.path.getsize(filename_zip) / B2MB   
            os.remove(filename_zip)            

        if ii_print and ii_verbose:
            if (j + 1) % write_int == 0 or j == nfiles - 1:
                t_accum = time.perf_counter() - t00
                rate = ((j+1)*ntasked/t_accum)
                bytes2bits = 8
                bandwidth_Mbps = rate * file_size_MB * ntasked * bytes2bits
                estimate_total_time = nfiles * ntasked / rate
                report_usage()
                msg = f"\n{(j+1)*ntasked} dataframes converted out of {nfiles*ntasked}\n"
                msg += f"rate             {rate:.2f} files/s\n"
                msg += f"df conversion    {t_df:.2f}s\n"
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
    if FCST_CYCLE is None:
        filename = f'{vpu}_forcings.nc'
    else:
        filename = f'ngen.{FCST_CYCLE}z.{URLBASE}.forcing.{LEAD_START}_{LEAD_END}.{vpu}.nc'
    if storage_type == 's3':
        s3_client = boto3.session.Session().client("s3")
        nc_filename = forcing_path + "/" + filename
    else:
        nc_filename = Path(forcing_path,filename)

    data = np.transpose(data,(2,1,0))

    t_utc = np.array([datetime.timestamp(datetime.strptime(jt,'%Y-%m-%d %H:%M:%S')) for jt in t_ax],dtype=np.float64)

    catchments = np.array(catchments,dtype='str')
    import netCDF4 as nc

    if storage_type == 's3':
        bucket, key = convert_url2key(nc_filename,'s3')
        with tempfile.NamedTemporaryFile(suffix='.nc') as tmpfile:
            with nc.Dataset(tmpfile.name, 'w', format='NETCDF4') as ds:
                ds.createDimension('catchment-id', len(catchments))
                ds.createDimension('time', len(t_utc))
                ids_var = ds.createVariable('ids', str, ('catchment-id',))
                time_var = ds.createVariable('Time', 'f8', ('catchment-id', 'time'))
                ugrd_var = ds.createVariable('UGRD_10maboveground', 'f4', ('catchment-id', 'time'))
                vgrd_var = ds.createVariable('VGRD_10maboveground', 'f4', ('catchment-id', 'time'))
                dlwrf_var = ds.createVariable('DLWRF_surface', 'f4', ('catchment-id', 'time'))
                apcp_var = ds.createVariable('APCP_surface', 'f4', ('catchment-id', 'time'))
                precip_var = ds.createVariable('precip_rate', 'f4', ('catchment-id', 'time'))
                tmp_var = ds.createVariable('TMP_2maboveground', 'f4', ('catchment-id', 'time'))
                spfh_var = ds.createVariable('SPFH_2maboveground', 'f4', ('catchment-id', 'time'))
                pres_var = ds.createVariable('PRES_surface', 'f4', ('catchment-id', 'time'))
                dswrf_var = ds.createVariable('DSWRF_surface', 'f4', ('catchment-id', 'time'))
                ids_var[:] = catchments
                time_var[:, :] = np.tile(t_utc, (len(catchments), 1))
                ugrd_var[:, :] = data[:, 0, :]
                vgrd_var[:, :] = data[:, 1, :]
                dlwrf_var[:, :] = data[:, 2, :]
                apcp_var[:, :] = data[:, 3, :]
                precip_var[:, :] = data[:, 4, :]
                tmp_var[:, :] = data[:, 5, :]
                spfh_var[:, :] = data[:, 6, :]
                pres_var[:, :] = data[:, 7, :]
                dswrf_var[:, :] = data[:, 8, :]
            netcdf_cat_file_size = os.path.getsize(tmpfile.name) / B2MB
            tmpfile.flush()
            tmpfile.seek(0)
            print(f"Uploading netcdf forcings to S3: bucket={bucket}, key={key}")
            s3_client.upload_file(tmpfile.name, bucket, key)

    else:
        with nc.Dataset(nc_filename, 'w', format='NETCDF4') as ds:
            ds.createDimension('catchment-id', len(catchments))
            ds.createDimension('time', len(t_utc))
            ids_var = ds.createVariable('ids', str, ('catchment-id',))
            time_var = ds.createVariable('Time', 'f8', ('catchment-id', 'time'))
            ugrd_var = ds.createVariable('UGRD_10maboveground', 'f4', ('catchment-id', 'time'))
            vgrd_var = ds.createVariable('VGRD_10maboveground', 'f4', ('catchment-id', 'time'))
            dlwrf_var = ds.createVariable('DLWRF_surface', 'f4', ('catchment-id', 'time'))
            apcp_var = ds.createVariable('APCP_surface', 'f4', ('catchment-id', 'time'))
            precip_var = ds.createVariable('precip_rate', 'f4', ('catchment-id', 'time'))
            tmp_var = ds.createVariable('TMP_2maboveground', 'f4', ('catchment-id', 'time'))
            spfh_var = ds.createVariable('SPFH_2maboveground', 'f4', ('catchment-id', 'time'))
            pres_var = ds.createVariable('PRES_surface', 'f4', ('catchment-id', 'time'))
            dswrf_var = ds.createVariable('DSWRF_surface', 'f4', ('catchment-id', 'time'))
            ids_var[:] = catchments
            time_var[:, :] = np.tile(t_utc, (len(catchments), 1))
            ugrd_var[:, :] = data[:, 0, :]
            vgrd_var[:, :] = data[:, 1, :]
            dlwrf_var[:, :] = data[:, 2, :]
            apcp_var[:, :] = data[:, 3, :]
            precip_var[:, :] = data[:, 4, :]
            tmp_var[:, :] = data[:, 5, :]
            spfh_var[:, :] = data[:, 6, :]
            pres_var[:, :] = data[:, 7, :]
            dswrf_var[:, :] = data[:, 8, :]
        print(f'netcdf has been written to {nc_filename}')  
        netcdf_cat_file_size = os.path.getsize(nc_filename) / B2MB

    return netcdf_cat_file_size  

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

    netcdf_cat_file_sizes = []
    with cf.ProcessPoolExecutor(max_workers=min(len(jcatchment_dict),nprocs)) as pool:
        for results in pool.map(
            write_netcdf,
            data_list, 
            vpu_list, 
            t_ax_list,
            catchments_list):
            netcdf_cat_file_sizes.append(results)

    return netcdf_cat_file_sizes

def write_df(df, filename, storage_type, s3=None, bucket=None, key_prefix=None, local_path=None):
    """
    Write a DataFrame to S3 or local storage as a CSV or Parquet file.
    The file type is inferred from the filename extension.

    Args:
        df (pd.DataFrame): DataFrame to write.
        filename (str): Name of the file (e.g., 'metadata.csv' or 'metadata.parquet').
        storage_type (str): 's3' or 'local'.
        s3 (boto3.client, optional): S3 client if using S3.
        bucket (str, optional): S3 bucket name.
        key_prefix (str, optional): S3 key prefix (folder path).
        local_path (str, optional): Local directory path.
    """
    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        if storage_type == 's3':
            buf = BytesIO()
            df.to_csv(buf, index=False)
            key_name = f"{key_prefix}/{filename}"
            s3.put_object(Bucket=bucket, Key=key_name, Body=buf.getvalue())
            buf.close()
        else:
            out_path = Path(local_path, filename)
            df.to_csv(out_path, index=False)
    elif ext == ".parquet":
        if storage_type == 's3':
            buf = BytesIO()
            df.to_parquet(buf, index=False)
            key_name = f"{key_prefix}/{filename}"
            s3.put_object(Bucket=bucket, Key=key_name, Body=buf.getvalue())
            buf.close()
        else:
            out_path = Path(local_path, filename)
            df.to_parquet(out_path, index=False)
    else:
        raise ValueError("Only CSV and Parquet output is supported by write_df")

def prep_ngen_data(conf):
    """
    Primary function to retrieve forcing data and convert it into files that can be ingested into ngen.

    Inputs: forcingprocessor config file https://github.com/CIROH-UA/ngen-datastream/blob/main/forcingprocessor/configs/conf_fp.json

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

    if type(gpkg_file) is not list: gpkg_files = [gpkg_file]
    else: gpkg_files = gpkg_file    

    global output_path, output_file_type
    output_path = conf["storage"].get("output_path","")
    output_file_type = conf["storage"].get("output_file_type","csv") 

    global ii_verbose, nprocs
    ii_verbose = conf["run"].get("verbose",False) 
    ii_collect_stats = conf["run"].get("collect_stats",True)
    nprocs = conf["run"].get("nprocs",int(os.cpu_count() * 0.5))

    global ii_plot, nts_plot, ngen_vars_plot
    ii_plot = conf.get("plot",False)
    if ii_plot: 
        nts_plot = conf["plot"].get("nts_plot",10)
        ngen_vars_plot = conf["plot"].get("ngen_vars",ngen_variables)
    else:
        nts_plot = 0
        ngen_vars_plot = []

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
        assert not ("parquet" in output_file_type and "csv" in output_file_type), "Both parquet and csv cannot be simultaneously specified in output_file_type, pick one."
    global storage_type
    if "s3://" in output_path:
        storage_type = "s3"
    elif "google" in output_path:
        storage_type = "google"
    else:
        storage_type = "local"

    nwm_forcing_files = []
    with open(nwm_file,'r') as fp:
        for jline in fp.readlines():
            nwm_forcing_files.append(jline.strip())
    nfiles = len(nwm_forcing_files)         

    log_time("CONFIGURATION_END", log_file)

    log_time("READWEIGHTS_START", log_file) 
    tw = time.perf_counter()
    if ii_verbose: print(f'Obtaining weights\n',flush=True) 
    global weights_df
    weights_df, jcatchment_dict = multiprocess_hf2ds(gpkg_files,nwm_forcing_files[0],nprocs)
    log_time("READWEIGHTS_END", log_file)

    # # conus hack
    # x = {}
    # x_list = []
    # for jdict in jcatchment_dict:
    #     [x_list.append(x) for x in jcatchment_dict[jdict]]
    # x['conus'] = x_list
    # jcatchment_dict = x

    log_time("CALC_WINDOW_START", log_file)
    ncatchments = len(weights_df)
    global x_min, x_max, y_min, y_max
    x_min, x_max, y_min, y_max = get_window(weights_df)
    weight_time = time.perf_counter() - tw
    log_time("CALC_WINDOW_END", log_file)

    log_time("STORE_METADATA_START", log_file)            
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
        cp_cmd = f'cp {nwm_file} {metaf_path}'
        os.system(cp_cmd)
        weights_df.to_parquet(os.path.join(metaf_path,"weights.parquet"))

    elif storage_type == "s3":
        bucket_path  = output_path
        forcing_path = bucket_path
        meta_path    = bucket_path + '/metadata'
        metaf_path   = bucket_path + '/metadata/forcings_metadata'
        bucket, key  = convert_url2key(metaf_path,storage_type)
        conf_path    = f"{key}/conf_fp.json"
        filenamelist_path = f"{key}/{os.path.basename(nwm_file)}"
        s3 = boto3.client("s3")          
        s3.put_object(
                Body=json.dumps(conf),
                Bucket=bucket,
                Key=conf_path
            )
        s3.upload_file(
                nwm_file,
                bucket,
                filenamelist_path
            )
        buf = BytesIO()
        filename = metaf_path + f"/weights.parquet" 
        weights_df.to_parquet(buf, index=False)         
        buf.seek(0)                  
        s3.put_object(Bucket=bucket, Key="/".join(filename.split('/')[3:]), Body=buf.getvalue())    

    log_time("STORE_METADATA_END", log_file)                 

    # s3://noaa-nwm-pds/nwm.20241029/forcing_short_range/nwm.t00z.short_range.forcing.f001.conus.nc
    pattern = r"nwm\.(\d{8})/forcing_(\w+)/nwm\.(\w+)(\d{2})z\.\w+\.forcing\.(\w+)(\d{2})\.conus\.nc"

    # Extract forecast cycle and lead time from the first and last file names
    global URLBASE, FCST_CYCLE, LEAD_START, LEAD_END
    match = re.search(pattern, nwm_forcing_files[0])
    FCST_CYCLE=None
    LEAD_START=None
    LEAD_END=None
    if match:
        URLBASE = match.group(2)
        FCST_CYCLE = match.group(3) + match.group(4)
        LEAD_START = match.group(5) + match.group(6)
    else:
        print(f"Could not extract forecast cycle and lead start from the first NWM forcing file: {nwm_forcing_files[0]}")
    match = re.search(pattern, nwm_forcing_files[-1])
    if match:
        LEAD_END = match.group(5) + match.group(6)  
    else:
        print(f"Could not extract lead end from the last NWM forcing file: {nwm_forcing_files[-1]}")

    # Determine the file system type based on the first NWM forcing file
    global fs_type
    if 's3://' in nwm_forcing_files[0] in nwm_forcing_files[0]:
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

    log_time("PROCESSING_START", log_file)
    t0 = time.perf_counter()
    if ii_verbose: print(f'Entering data extraction...\n',flush=True)   
    # data_array, t_ax, nwm_data, nwm_file_sizes_MB = forcing_grid2catchment(nwm_forcing_files, fs)
    # data_array=data_array[0][None,:]
    # t_ax = t_ax
    # nwm_data=nwm_data[0][None,:]
    data_array, t_ax, nwm_data, nwm_file_sizes_MB = multiprocess_data_extract(nwm_forcing_files,nprocs,weights_df,fs)

    if datetime.strptime(t_ax[0],'%Y-%m-%d %H:%M:%S') > datetime.strptime(t_ax[-1],'%Y-%m-%d %H:%M:%S'):
        # Hack to ensure data is always written out with time moving forward.
        t_ax=list(reversed(t_ax))
        data_array = np.flip(data_array,axis=0)
        tmp = LEAD_START
        LEAD_START = LEAD_END
        LEAD_END = tmp

    t_extract = time.perf_counter() - t0
    complexity = (nfiles * ncatchments) / 10000
    score = complexity / t_extract
    if ii_verbose: print(f'Data extract processs: {nprocs:.2f}\nExtract time: {t_extract:.2f}\nComplexity: {complexity:.2f}\nScore: {score:.2f}\n', end=None,flush=True)
    log_time("PROCESSING_END", log_file)

    log_time("FILEWRITING_START", log_file)
    t0 = time.perf_counter()
    if "netcdf" in output_file_type:
        netcdf_cat_file_sizes_MB = multiprocess_write_netcdf(data_array, jcatchment_dict, t_ax)
    if ii_verbose: print(f'Writing catchment forcings to {output_path}!', end=None,flush=True)  
    forcing_cat_ids, dfs, filenames, individual_cat_file_sizes_MB, individual_cat_file_sizes_MB_zipped, tar_buffs = multiprocess_write(data_array,t_ax,list(weights_df.index),nprocs,forcing_path)

    write_time += time.perf_counter() - t0    
    write_rate = ncatchments / write_time
    if ii_verbose: print(f'\n\nWrite processs: {nprocs}\nWrite time: {write_time:.2f}\nWrite rate {write_rate:.2f} files/second\n', end=None,flush=True)
    log_time("FILEWRITING_END", log_file)

    runtime = time.perf_counter() - t_start

    if ii_plot:
        if gpkg_files[0].endswith('.parquet'): 
            print(f'Plotting currently not implemented for parquet, need geopackage')
        else:

            if len(gpkg_files) > 1: 
                raise Warning(f'Plotting only the first geopackage {gpkg_files[0]}')

            cat_ids = ['cat-' + x for x in forcing_cat_ids]
            jplot_vars = np.array([x for x in range(len(ngen_variables)) if ngen_variables[x] in ngen_vars_plot])
            if storage_type == "s3":
                gif_out = './GIFs'
            else:
                gif_out = Path(meta_path,'GIFs')
            plot_ngen_forcings(nwm_data, data_array[:,jplot_vars,:], gpkg_files[0], t_ax, cat_ids, ngen_vars_plot, gif_out)
            if storage_type == "s3":
                sync_cmd = f'aws s3 sync ./GIFs {meta_path}/GIFs'
                os.system(sync_cmd)
    
    # Metadata        
    if ii_collect_stats:
        log_time("METADATA_START", log_file)
        t000 = time.perf_counter()
        if ii_verbose: print(f'Data processing, now calculating metadata...',flush=True)                     

        nwm_file_size_avg = np.average(nwm_file_sizes_MB)
        nwm_file_size_med = np.median(nwm_file_sizes_MB)
        nwm_file_size_std = np.std(nwm_file_sizes_MB)

        individual_catch_file_size_avg = 0
        individual_catch_file_size_med = 0
        individual_catch_file_size_std = 0
        individual_catch_file_zip_size_avg = 0
        individual_catch_file_zip_size_med = 0
        individual_catch_file_zip_size_std = 0
        if "csv" in output_file_type or "parquet" in output_file_type:
            individual_catch_file_size_avg = np.average(np.fromiter(individual_cat_file_sizes_MB, dtype=float))
            individual_catch_file_size_med = np.median(individual_cat_file_sizes_MB)
            individual_catch_file_size_std = np.std(individual_cat_file_sizes_MB)

            individual_catch_file_zip_size_avg = np.average(individual_cat_file_sizes_MB_zipped)
            individual_catch_file_zip_size_med = np.median(individual_cat_file_sizes_MB_zipped)
            individual_catch_file_zip_size_std = np.std(individual_cat_file_sizes_MB_zipped) 

        netcdf_catch_file_size_avg = 0
        netcdf_catch_file_size_med = 0
        netcdf_catch_file_size_std = 0
        if "netcdf" in output_file_type:
            netcdf_catch_file_size_avg = np.average(np.fromiter(netcdf_cat_file_sizes_MB, dtype=float))
            netcdf_catch_file_size_med = np.median(netcdf_cat_file_sizes_MB)
            netcdf_catch_file_size_std = np.std(netcdf_cat_file_sizes_MB)            

        metadata = {        
            "runtime_s"               : [round(runtime,2)],
            "nvars_intput"            : [len(nwm_variables)],               
            "nwmfiles_input"          : [len(nwm_forcing_files)],           
            "nwm_file_size_avg_MB"    : [nwm_file_size_avg],
            "nwm_file_size_med_MB"    : [nwm_file_size_med],
            "nwm_file_size_std_MB"    : [nwm_file_size_std],
            "catch_files_output"      : [nfiles],
            "nvars_output"            : [len(ngen_variables)],
            "individual_catch_file_size_avg_MB"  : [individual_catch_file_size_avg],
            "individual_catch_file_size_med_MB"  : [individual_catch_file_size_med],
            "individual_catch_file_size_std_MB"  : [individual_catch_file_size_std],
            "individual_catch_file_zip_size_avg_MB" : [individual_catch_file_zip_size_avg],
            "individual_catch_file_zip_size_med_MB" : [individual_catch_file_zip_size_med],
            "individual_catch_file_zip_size_std_MB" : [individual_catch_file_zip_size_std],   
            "netcdf_catch_file_size_avg_MB"  : [netcdf_catch_file_size_avg],
            "netcdf_catch_file_size_med_MB"  : [netcdf_catch_file_size_med],
            "netcdf_catch_file_size_std_MB"  : [netcdf_catch_file_size_std]                                                      
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

        write_df(metadata_df, "metadata.csv", storage_type, local_path=metaf_path)
        write_df(avg_df, "catchments_avg.csv", storage_type, local_path=metaf_path)
        write_df(med_df, "catchments_median.csv", storage_type, local_path=metaf_path)

        meta_time = time.perf_counter() - t000
        log_time("METADATA_END", log_file)

    if "tar" in output_file_type:
        log_time("TAR_START", log_file)
        if ii_verbose: print(f'\nWriting tarball...',flush=True)
        t0000 = time.perf_counter()
        multiprocess_write_tars(dfs,jcatchment_dict,filenames,tar_buffs)    
        tar_time = time.perf_counter() - t0000
        log_time("TAR_END", log_file)

    if ii_verbose:
        print(f"\n\n--------SUMMARY-------")
        msg = f"\nData has been written to {output_path}"
        msg += f"\nCalc weights  : {weight_time:.2f}s"
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

    if storage_type == "s3": 
        bucket, key  = convert_url2key(metaf_path,storage_type)
        log_path = key + '/profile_fp.txt'
        s3.upload_file(
                f'./profile_fp.txt',
                bucket,
                log_path
            )
    else:
        os.system(f"mv ./profile_fp.txt {metaf_path}")    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        dest="infile", type=str, help="A json containing user inputs to run forcingprocessor"
    )
    args = parser.parse_args()

    if args.infile[0] == '{':
        conf = json.loads(args.infile)
    else:
        if 's3://' in args.infile:
            os.system(f'wget {args.infile}')
            filename = args.infile.split('/')[-1]
            conf = json.load(open(filename))
        else:
            conf = json.load(open(args.infile))

    prep_ngen_data(conf)
