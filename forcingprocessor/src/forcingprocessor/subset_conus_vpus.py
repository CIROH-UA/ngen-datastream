import os, re, copy, json, argparse
import geopandas as gpd
from forcingprocessor.weights_hf2ds import calc_weights_from_gdf

def subset_conus2vpus(conus:str,raster_file:str,output_dir:str) -> None:
    # Given a conus hydrofabric, subset into vpu and create weights

    PATTERN_VPU = r'\$VPU'

    layers = gpd.list_layers(conus)
    print(layers)

    VPUs = ["01","02","03N",
        "03S","03W","04",
        "05","06", "07",
        "08","09","10L",
        "10U","11","12",
        "13","14","15",
        "16","17","18",]

    jfile_template = os.path.join(output_dir,"nextgen_$VPU.gpkg")    
    for j,jvpu in enumerate(VPUs):
        tmpl_cpy = copy.deepcopy(jfile_template)
        jfile = re.sub(PATTERN_VPU, jvpu, tmpl_cpy)    

        for jlayer in layers['name']:    
            print(f'subsetting layer {jlayer} for vpu {jvpu}')
            data_conus_jlayer = gpd.read_file(conus, layer=jlayer)  
            data_jvpu = gpd.GeoDataFrame(data_conus_jlayer[data_conus_jlayer['vpuid'] == jvpu])
            data_jvpu = gpd.GeoDataFrame(data_conus_jlayer[data_conus_jlayer['type'] != "coastal"])
            data_jvpu.to_file(jfile,layer=jlayer)

            if jlayer == "divides":

                weights_json = calc_weights_from_gdf(data_jvpu, raster_file)
                jfile_weights_template = os.path.join(output_dir,"nextgen_$VPU_weights.json")
                tmpl_cpy = copy.deepcopy(jfile_weights_template)
                jfile_weights = re.sub(PATTERN_VPU, jvpu, tmpl_cpy)

                with open(jfile_weights,'w') as fp:
                    json.dump(weights_json,fp)
    
if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--conus_file", help="Path to a conus geopackage",default="")
    parser.add_argument("--raster_file",  help="Path to example nwm CONUS forcing file",default="")
    parser.add_argument("--output_dir",  help="Path to write to",default="./")
    args = parser.parse_args()

    subset_conus2vpus(args.conus_file, args.raster_file, args.output_dir)