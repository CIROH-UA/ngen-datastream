import os, re, copy, json, argparse
import geopandas as gpd
from forcingprocessor.weights_hf2ds import calc_weights_from_gdf
import concurrent.futures as cf
import numpy as np

def multi_subset_conus2vpus(conus:str,raster_file:str,output_dir:str):
    VPUs = [
    "01","02","03N",
    "03S","03W","04",
    "05","06", "07",
    "08","09","10L",
    "10U","11","12",
    "13","14","15",
    "16","17","18",]

    nprocs = 3
    nVPUs = len(VPUs)
    VPUs_list = []
    nper = nVPUs // nprocs
    nleft = nVPUs - (nper * nprocs) 
    conus_list = []
    raster_list = []
    output_dir_list = []  
    i = 0
    k = nper
    for j in range(nprocs):
        if j < nleft: k += 1
        VPUs_list.append(VPUs[i:k])
        conus_list.append(conus)
        raster_list.append(raster_file)
        output_dir_list.append(output_dir)
        i=k
        k = nper + i
        
    with cf.ProcessPoolExecutor(max_workers=nprocs) as pool:
        for results in pool.map(
        subset_conus2vpus,
        conus_list,
        raster_list,
        output_dir_list,
        VPUs_list
        ):   
            pass

def subset_conus2vpus(conus:str,raster_file:str,output_dir:str, VPUs : list) -> None:
    # Given a conus hydrofabric, subset into vpu and create weights

    PATTERN_VPU = r'\$VPU'

    layers = gpd.list_layers(conus)
    layer_names = list(layers['name'])
    print(layer_names)


    jfile_template = os.path.join(output_dir,"nextgen_VPU_$VPU.gpkg")    
    for j,jvpu in enumerate(VPUs):
        txt_file = []
        txt_file2 = []        
        ncats = 0
        nattrs = 0
        tmpl_cpy = copy.deepcopy(jfile_template)
        jfile = re.sub(PATTERN_VPU, jvpu, tmpl_cpy)    

        for jlayer in layer_names:  
            if jlayer == "divides" or jlayer == "divide-attributes":  
                print(f'subsetting layer {jlayer} for vpu {jvpu}')
                data_conus_jlayer = gpd.read_file(conus, layer=jlayer)  
                data_jvpu_jlayer = gpd.GeoDataFrame(data_conus_jlayer[data_conus_jlayer['vpuid'] == jvpu])
                if jlayer == "divides":
                    divides_df = data_jvpu_jlayer
                    ncats = len(divides_df)
                elif jlayer == "divide-attributes":
                    attrs_df = data_jvpu_jlayer
                    # There exists divide_id's with the values that contain patterns like "1e+05"
                    # This HACK removes any row for which the divide_id contains a "+"
                    attrs_df = gpd.GeoDataFrame(attrs_df.drop(attrs_df.index[list(np.where(["+" in x for x in list(attrs_df['divide_id'])])[0])]))
                    nattrs = len(attrs_df)
                    if nattrs != ncats:
                        # HACK
                        # There are some divide_id values that do not have corresponding divide-attributes.
                        # For now these are removed, but this should be revisted

                        cats_in_attrs = attrs_df['divide_id'].to_list()
                        cats_in_divides = divides_df['divide_id'].to_list()
                                            
                        for jcat_in_attr in cats_in_attrs:
                            if jcat_in_attr not in cats_in_divides:
                                attrs_df = gpd.GeoDataFrame(attrs_df[attrs_df['divide_id'] != jcat_in_attr])
                                divides_df = gpd.GeoDataFrame(divides_df[divides_df['divide_id'] != jcat_in_attr])
                                txt_file2.append(jcat_in_attr + "\n")

                        cats_in_attrs = attrs_df['divide_id'].to_list()

                        for jcat_in_divides in cats_in_divides:
                            if jcat_in_divides not in cats_in_attrs:
                                attrs_df = gpd.GeoDataFrame(attrs_df[attrs_df['divide_id'] != jcat_in_divides])
                                divides_df = gpd.GeoDataFrame(divides_df[divides_df['divide_id'] != jcat_in_divides])
                                txt_file.append(jcat_in_divides + "\n")
                        ncats = len(divides_df)
                        nattrs = len(attrs_df)

                        assert ncats == nattrs,f"VPU {jvpu} ncats {ncats} nattrs {nattrs}"

                        # attrs_df.to_file(jfile,layer="divide-attributes")
                        # divides_df.to_file(jfile,layer='divides')

                    ii_do_weights = False
                    if ii_do_weights:
                        print(f'Weights calc for VPU {jvpu}')
                        weights_json = calc_weights_from_gdf(divides_df, raster_file)
                        jfile_weights_template = os.path.join(output_dir,"nextgen_VPU_$VPU_weights.json")
                        tmpl_cpy = copy.deepcopy(jfile_weights_template)
                        jfile_weights = re.sub(PATTERN_VPU, jvpu, tmpl_cpy)

                        with open(jfile_weights,'w') as fp:
                            json.dump(weights_json,fp)   

                    else:
                        pass
                        # attrs_df.to_file(jfile,layer="divide-attributes")
                        # divides_df.to_file(jfile,layer='divides')                    
                else:
                    pass
                    # data_jvpu_jlayer.to_file(jfile,layer=jlayer)

        if len(txt_file) > 0:
            with open(os.path.join(output_dir,f"missing_catchment_attrs_{jvpu}.txt"),mode='w') as fp:
                fp.writelines(txt_file)
        if len(txt_file2) > 0:
            with open(os.path.join(output_dir,f"missing_catchment_divides_{jvpu}.txt"),mode='w') as fp:
                fp.writelines(txt_file2)            
    
if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--conus_file", help="Path to a conus geopackage",default="")
    parser.add_argument("--raster_file",  help="Path to example nwm CONUS forcing file",default="")
    parser.add_argument("--output_dir",  help="Path to write to",default="./")
    args = parser.parse_args()

    VPUs = [
    "01","02","03N",
    "03S","03W","04",
    "05","06", "07",
    "08","09","10L",
    "10U","11","12",
    "13","14","15",
    "16","17","18",]   

    # multi_subset_conus2vpus(args.conus_file, args.raster_file, args.output_dir)
    subset_conus2vpus(args.conus_file, args.raster_file, args.output_dir,VPUs)