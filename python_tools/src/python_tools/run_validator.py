import os, argparse
from ngen.config.realization import NgenRealization
from ngen.config.validate import validate_paths
import re
import xarray as xr
import geopandas as gpd
gpd.options.io_engine = "pyogrio"
import pandas as pd
from datetime import datetime, timezone
import concurrent.futures as cf

def check_forcings(forcings_start,forcings_end,n):
    start_time = serialized_realization.time.start_time
    end_time   = serialized_realization.time.end_time
    dt_s = serialized_realization.time.output_interval
    if forcings_end == forcings_start:
        dt_forcings_s = 3600
    else:
        dt_forcings_s = (forcings_end - forcings_start).total_seconds() / (n - 1)
    assert start_time == forcings_start, f"Realization start time {start_time} does not match forcing start time {forcings_start}"
    assert end_time == forcings_end, f"Realization end time {end_time} does not match forcing end time {forcings_end}"
    assert dt_s == dt_forcings_s, f"Realization output_interval {dt_s} does not match forcing time axis {dt_forcings_s}"    


def validate_realization(realization_file):
    """
    Validates
    1) Realization files meets pydantic model as defined in ngen-cal
    2) Paths given in file exist
    """
    relative_dir     = os.path.dirname(os.path.dirname(realization_file))

    print(f'Done\nValidating {realization_file}',flush = True)
    serialized_realization = NgenRealization.parse_file(realization_file)
    serialized_realization.resolve_paths(relative_to=relative_dir)
    val = validate_paths(serialized_realization)
    if len(val) > 1:
        for jval in val:
            model = jval.model
            print(val)
            print(model)
    
    return serialized_realization, relative_dir

def validate_catchment_files(validations, catchments):
    """
    General function to validate any files that need to be associated with a catchment

    Inputs:
    validations: dictionary of list of patterns and files to match. Each list should be a 1:1 correspondence between a catchment and it's file.
    Multiple lists are allowed to allow for multiple file types (forcings, ngen configs like CFE)
    Validates 
    1) file names match realization file description
    2) files exist for each catchment in geojson
    3) start/end times and interval match realization file
    """
    
    for jval in validations:
        pattern     = validations[jval]['pattern']
        files       = validations[jval]['files']
        if len(files) == 0:
            continue
        if jval == "forcing":
            if files[0].endswith(".nc"):
                nc_file = files[0]
                if not os.path.exists(nc_file): 
                    raise Exception(f"Forcings file not found!")
                with xr.open_dataset(os.path.join(forcing_dir,nc_file)) as ngen_forcings:
                    df = ngen_forcings['precip_rate']
                    forcings_start = datetime.fromtimestamp(ngen_forcings.Time.values[0,0],timezone.utc)
                    forcings_end   = datetime.fromtimestamp(ngen_forcings.Time.values[0,-1],timezone.utc)
                    check_forcings(forcings_start,forcings_end,len(ngen_forcings.time.values))
                    continue

        for j, jcatch in enumerate(catchments):    
            jcatch_pattern = pattern.replace('{{id}}',jcatch)
            compiled       = re.compile(jcatch_pattern)      

            jfile = files[j]     
            if not bool(compiled.match(jfile)):
                raise Exception(f"{jcatch} -> File {jfile} does not match pattern specified {pattern}")

            if jval == "forcing":
                if j == 0:
                    full_path = os.path.join(forcing_dir,files[0])
                    df = pd.read_csv(full_path)
                    forcings_start = datetime.strptime(df['time'].iloc[0],'%Y-%m-%d %H:%M:%S')
                    forcings_end   = datetime.strptime(df['time'].iloc[-1],'%Y-%m-%d %H:%M:%S')
                    check_forcings(forcings_start,forcings_end,len(df['time']))

def validate_data_dir(data_dir):

    realization_file = None
    geopackage_file  = None
    for path, _, files in os.walk(data_dir):
        for jfile in files:
            jfile_path = os.path.join(path,jfile)
            if jfile_path.find('realization') >= 0: 
                if realization_file is None: 
                    realization_file = jfile_path
                else: 
                    raise Exception('This run directory contains more than a single realization file, remove all but one.')
            if jfile_path.find('.gpkg') >= 0: 
                if geopackage_file is None: 
                    geopackage_file = jfile_path
                else: 
                    raise Exception('This run directory contains more than a single geopackage file, remove all but one.')                    

    if realization_file is None: 
        raise Exception(f"Did not find realization file in ngen-run/config!!!")
    print(f'Realization found! Retrieving catchment data...',flush = True)

    if geopackage_file is None: 
        raise Exception(f"Did not find geopackage file in ngen-run/config!!!")    

    catchments     = gpd.read_file(geopackage_file, layer='divides')
    catchment_list = sorted(list(catchments['divide_id']))

    global serialized_realization
    serialized_realization, relative_dir = validate_realization(realization_file)    

    print(f'Done\nValidating required individual catchment paths',flush = True)
    global forcing_dir, config_dir, validate_type_names
    forcing_dir    = os.path.join(relative_dir,serialized_realization.global_config.forcing.path)
    config_dir     = os.path.join(data_dir,"config","cat_config")
    if os.path.isdir(forcing_dir):
        forcing_files  = [x for _,_,x in os.walk(forcing_dir)]
        if len(forcing_files) == 0: 
            raise Exception(f"No forcing files in {forcing_dir}")
        elif len(forcing_files) == 1:
            forcing_files = [os.path.join(forcing_dir,forcing_files[0][0])]
        else:
            forcing_files  = sorted(forcing_files[0])                   
    else:
        forcing_files = [forcing_dir]
        nc_file = forcing_files[0]
        if not os.path.exists(nc_file): 
            raise Exception(f"Forcings file not found!")

    jdir_dict = {"CFE":"CFE",
                 "PET":"PET",
                 "NoahOWP":"NOAH-OWP-M"}

    validate_files = {"forcing":{"pattern":serialized_realization.global_config.forcing.file_pattern,"files": forcing_files}}
    serialized_realization = NgenRealization.parse_file(realization_file)
    serialized_realization.time.start_time = serialized_realization.time.start_time.replace(tzinfo=timezone.utc)
    serialized_realization.time.end_time = serialized_realization.time.end_time.replace(tzinfo=timezone.utc)
    for jform in serialized_realization.global_config.formulations:
        for jmod in jform.params.modules:
            if jmod.params.model_name == "SLOTH": continue
            jdir = jdir_dict[jmod.params.model_name]
            jconfig_dir = os.path.join(config_dir,jdir)
            config_files   = [os.path.join(f"config/cat_config/{jdir}",x) for x in [x for _,_,x in os.walk(jconfig_dir)][0]]
            pattern = str(jmod.params.config)
            jcatch_pattern = pattern.replace('{{id}}',r'[^/]+')
            compiled       = re.compile(jcatch_pattern) 
            validate_files[jmod.params.model_name] = {"pattern":pattern,"files":sorted([x for x in config_files if bool(compiled.match(x))])}

    if serialized_realization.routing:
        troute_path = os.path.join(data_dir,serialized_realization.routing.config)
        assert os.path.exists(troute_path), "t-route specified in config, but not found"

    nprocs = os.cpu_count()
    val_dict_list = []
    catchment_list_list = []
    ncatchments = len(catchment_list)
    nper = ncatchments // nprocs
    nleft = ncatchments - (nper * nprocs)
    i = 0
    k = 0
    for _ in range(nprocs):
        k = nper + i + nleft   
        tmp_dict = {}
        for jval in validate_files:    
            tmp_dict[jval] = {}
            tmp_dict[jval]['pattern'] = validate_files[jval]['pattern']
            tmp_dict[jval]['files'] = validate_files[jval]['files'][i:k] 
        val_dict_list.append(tmp_dict)
        jcatchments = catchment_list[i:k]
        catchment_list_list.append(jcatchments)
        i = k
        
    # validate_catchment_files(val_dict_list[0],catchment_list_list[0])
    with cf.ProcessPoolExecutor() as pool:
        for results in pool.map(
            validate_catchment_files,
            val_dict_list,
            catchment_list_list):
            pass    

    print(f'\nNGen run folder is valid\n',flush = True)        

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data_dir",
        dest="data_dir", 
        type=str,
        help="Path to the ngen input data folder", 
        required=False
    )
    parser.add_argument(
        "--tarball",
        dest="tarball", 
        type=str, 
        help="Path to tarball to be validated as ngen input data folder", 
        required=False
    )
    args = parser.parse_args()

    if args.data_dir:
        data_dir = args.data_dir
        ii_delete_folder = False
    elif args.tarball:
        data_dir = '/tmp/ngen_data_dir'
        if os.path.exists(data_dir): 
            os.system(f'rm -rf {data_dir}')
        os.mkdir(data_dir)
        os.system(f'tar -xzf {args.tarball} -C {data_dir}')
        ii_delete_folder = True
    elif args.data_dir and args.tarball:
        raise Exception('Must specify either data folder path or tarball path, not both.')
    else:
        raise Exception('No options set!')
    
    assert os.path.exists(data_dir), f"{data_dir} is an invalid directory"

    validate_data_dir(data_dir)

    if ii_delete_folder: os.system('rm -rf /tmp/ngen_data_dir')