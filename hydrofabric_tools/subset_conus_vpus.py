import os, re, copy, json
import geopandas as gpd
import xarray as xr
import numpy as np
from exactextract import exact_extract
from exactextract.raster import NumPyRasterSource

data_path = "/home/jlaser/code/CIROH/ngen-datastream/data/"

conus = os.path.join(data_path,"hydrofabric/v2.2/conus_nextgen.gpkg")
output_dir = os.path.join(data_path,"hydrofabric/v2.2")
raster_file = os.path.join(data_path,"nwm.t00z.analysis_assim.forcing.tm00.conus.nc")

PATTERN_VPU = r'\$VPU'

raster_data = xr.open_dataset(raster_file)
xmin = raster_data.x[0]
xmax = raster_data.x[-1]
ymin = raster_data.y[0]
ymax = raster_data.y[-1]

projection = raster_data.crs.esri_pe_string

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
jfile_weights_template = os.path.join(output_dir,"nextgen_$VPU_weights.json")
for j,jvpu in enumerate(VPUs):
    tmpl_cpy = copy.deepcopy(jfile_template)
    jfile = re.sub(PATTERN_VPU, jvpu, tmpl_cpy)    

    for jlayer in layers['name']:    
        print(f'subsetting layer {jlayer} for vpu {jvpu}')
        data_conus_jlayer = gpd.read_file(conus, layer=jlayer)  
        data_jvpu = gpd.GeoDataFrame(data_conus_jlayer[data_conus_jlayer['vpuid'] == jvpu])
        data_jvpu.to_file(jfile,layer=jlayer)

        if jlayer == "divides":

            data_jvpu = data_jvpu.to_crs(projection)

            # Calc weights
            wkt = data_jvpu.crs.to_wkt()
            rastersource = NumPyRasterSource(
                    np.squeeze(raster_data["T2D"]), 
                    srs_wkt=wkt, 
                    xmin=xmin, 
                    xmax=xmax, 
                    ymin=ymin, 
                    ymax=ymax
                )    

            output = exact_extract(
                rastersource,
                data_jvpu,
                ["cell_id", "coverage"],
                include_cols=["divide_id"],
                output="pandas",
            )

            weights = output.set_index("divide_id")

            tmpl_cpy = copy.deepcopy(jfile_weights_template)
            jfile_weights = re.sub(PATTERN_VPU, jvpu, tmpl_cpy)
            weights.to_parquet(jfile_weights)
            out_json = {}
            for jcol in range(len(weights)):
                jcat = weights.index[jcol]
                jdata = weights[weights.index == jcat]
                cell_ids = jdata['cell_id'].values[0].tolist()
                coverage =  jdata['coverage'].values[0].tolist()
                out_json[jcat] = [cell_ids, coverage]

            with open(jfile_weights,'w') as fp:
                json.dump(out_json,fp)

            del weights, rastersource, wkt, out_json

        
        
