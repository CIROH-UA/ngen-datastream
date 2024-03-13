import geopandas as gpd
import pandas as pd
import argparse

from ngen.config_gen.file_writer import DefaultFileWriter
from ngen.config_gen.hook_providers import DefaultHookProvider
from ngen.config_gen.generate import generate_configs

from ngen.config_gen.models.cfe import Cfe
from ngen.config_gen.models.pet import Pet

def gen_pet_cfe(hf_file,hf_lnk_file,out):
    hf: gpd.GeoDataFrame = gpd.read_file(hf_file, layer="divides")
    hf_lnk_data: pd.DataFrame = pd.read_parquet(hf_lnk_file)
    hook_provider = DefaultHookProvider(hf=hf, hf_lnk_data=hf_lnk_data)
    file_writer = DefaultFileWriter(out)
    generate_configs(
        hook_providers=hook_provider,
        hook_objects=[Cfe, Pet],
        file_writer=file_writer,
    )

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
        help="Path to the .gpkg attributes", 
        required=False
    )    

    args = parser.parse_args()

    if '.txt' in args.hf_lnk_file:
        with open(args.hf_lnk_file,'r') as fp:
            data=fp.readlines()
            hf_lnk_file = data[0] 
    else:
        hf_lnk_file = args.hf_lnk_file

    gen_pet_cfe(args.hf_file,hf_lnk_file,args.outdir)
