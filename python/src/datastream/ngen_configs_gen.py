import geopandas as gpd
import pandas as pd
import argparse
import re
import pickle, copy
from pathlib import Path
gpd.options.io_engine = "pyogrio"

from ngen.config_gen.file_writer import DefaultFileWriter
from ngen.config_gen.hook_providers import DefaultHookProvider
from ngen.config_gen.generate import generate_configs

from ngen.config_gen.models.cfe import Cfe
from ngen.config_gen.models.pet import Pet

from ngen.config.realization import NgenRealization
from ngen.config.configurations import Routing

def gen_noah_owp_confs_from_pkl(pkl_file,out_dir,start,end):

    with open(pkl_file, 'rb') as fp:
        nom_dict = pickle.load(fp)

    for jcatch in nom_dict:
        jcatch_str = copy.deepcopy(nom_dict[jcatch])
        for j,jline in enumerate(jcatch_str):
            if "startdate" in jline:
                pattern = r'(startdate\s*=\s*")[0-9]{12}'
                jcatch_str[j] = re.sub(pattern, f"startdate        = \"{start.strftime('%Y%m%d%H%M')}", jline)
            if "enddate" in jline:
                pattern = r'(enddate\s*=\s*")[0-9]{12}'
                jcatch_str[j] =  re.sub(pattern, f"enddate          = \"{end.strftime('%Y%m%d%H%M')}", jline)

        with open(Path(out_dir,f"noah-owp-modular-init-{jcatch}.namelist.input"),"w") as fp:
            fp.writelines(jcatch_str)

def generate_troute_conf(out_dir,start,gpkg):

    template = Path(__file__).parent.parent.parent.parent/"configs/ngen/ngen.yaml"

    with open(template,'r') as fp:
        conf_template = fp.readlines()

    catchments     = gpd.read_file(gpkg, layer='divides')
    catchment_list = sorted(list(catchments['divide_id']))
    list_str=""
    for jcatch in catchment_list:
        list_str += (f"\n               - nex-{jcatch[4:]}_output.csv ")        
    list_str = list_str.strip('\n')
    troute_conf_str = conf_template
    for j,jline in enumerate(conf_template):
        if "start_datetime" in jline:
            pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
            troute_conf_str[j] = re.sub(pattern, start.strftime('%Y-%m-%d %H:%M:%S'), jline)           

        pattern = r'^\s*qlat_files\s*:\s*\[\]'
        if re.search(pattern,jline):
            troute_conf_str[j] = re.sub(pattern,  f"          qlat_files: {list_str}      ", jline)

    with open(Path(out_dir,"ngen.yaml"),'w') as fp:
        fp.writelines(troute_conf_str)  

def gen_petAORcfe(hf_file,hf_lnk_file,out,models):
    hf: gpd.GeoDataFrame = gpd.read_file(hf_file, layer="divides")
    hf_lnk_data: pd.DataFrame = pd.read_parquet(hf_lnk_file)
    hook_provider = DefaultHookProvider(hf=hf, hf_lnk_data=hf_lnk_data)
    file_writer = DefaultFileWriter(out)
    generate_configs(
        hook_providers=hook_provider,
        hook_objects=models,
        file_writer=file_writer,
    )

# Austin's multiprocess example from chat 3/25
# import concurrent.futures as cf
# from functools import partial
# def generate_configs_multiprocessing(
#     hook_providers: Iterable["HookProvider"],
#     hook_objects: Collection[BuilderVisitableFn],
#     file_writer: FileWriter,
#     pool: cf.ProcessPoolExecutor,
# ):
#     def capture(divide_id: str, bv: BuilderVisitableFn):
#         bld_vbl = bv()
#         bld_vbl.visit(hook_prov)
#         model = bld_vbl.build()
#         file_writer(divide_id, model)

#     div_hook_obj = DivideIdHookObject()
#     for hook_prov in hook_providers:
#         # retrieve current divide id
#         div_hook_obj.visit(hook_prov)
#         divide_id = div_hook_obj.divide_id()
#         assert divide_id is not None

#         fn = partial(capture, divide_id=divide_id)
#         pool.map(fn, hook_objects)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hf_file",
        dest="hf_file", 
        type=str,
        help="Path to the .gpkg", 
        required=False
    )
    parser.add_argument(
        "--hf_lnk_file",
        dest="hf_lnk_file", 
        type=str,
        help="Path to the .gpkg attributes", 
        required=False
    )
    parser.add_argument(
        "--outdir",
        dest="outdir", 
        type=str,
        help="Path to write ngen configs", 
        required=False
    )    
    parser.add_argument(
        "--pkl_file",
        dest="pkl_file", 
        type=str,
        help="Path to the noahowp pkl", 
        required=False
    )      
    parser.add_argument(
        "--realization",
        dest="realization", 
        type=str,
        help="Path to the ngen realization", 
        required=False
    )       

    args = parser.parse_args()

    if '.txt' in args.hf_lnk_file:
        with open(args.hf_lnk_file,'r') as fp:
            data=fp.readlines()
            hf_lnk_file = data[0] 
    else:
        hf_lnk_file = args.hf_lnk_file

    serialized_realization = NgenRealization.parse_file(args.realization)
    start = serialized_realization.time.start_time
    end   = serialized_realization.time.end_time
    models = []
    include = []
    ii_cfe_or_pet = False
    model_names = []
    for jform in serialized_realization.global_config.formulations:
        for jmod in jform.params.modules:
            model_names.append(jmod.params.model_name)

    if "PET" in model_names:
        models.append(Pet)
        include.append("PET")
        ii_cfe_or_pet = True            
    if "CFE" in model_names:
        models.append(Cfe)    
        include.append("CFE")
        ii_cfe_or_pet = True            

    if "NoahOWP" in model_names:
        if "pkl_file" in args:
            print(f'Generating NoahOWP configs from pickle',flush = True)
            gen_noah_owp_confs_from_pkl(args.pkl_file, args.outdir, start, end)
        else:
            raise Exception(f"Generating NoahOWP configs manually not implemented, create pkl.")            

    if ii_cfe_or_pet: 
        print(f'Generating {include} configs from pydantic models',flush = True)
        gen_petAORcfe(args.hf_file,hf_lnk_file,args.outdir,models)

    globals = [x[0] for x in serialized_realization]
    if serialized_realization.routing is not None:
        print(f'Generating t-route config from template',flush = True)
        generate_troute_conf(args.outdir,start,args.hf_file) 

    print(f'Done!',flush = True)