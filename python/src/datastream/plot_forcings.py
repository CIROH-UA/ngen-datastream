import xarray as xr
import argparse, os, json
import matplotlib as mpl
import matplotlib.pyplot as plt
import imageio.v2 as imageio
import numpy as np
import pandas as pd
import geopandas as gpd
plt.style.use('dark_background')
mpl.use('Agg')

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
    "precip_rate",  # HACK RAINRATE * 3600
    "TMP_2maboveground",        
    "SPFH_2maboveground",
    "PRES_surface",
    "DSWRF_surface",
] 

def plot_ngen_forcings(netcdf_files, geopackage, ngen_data, t_ax, catchment_ids, nwm_variable, ngen_variable, var_idx, domain):    
    gdf = gpd.read_file(geopackage, layer='divides')
    gdf = gdf.set_index('divide_id')
    gdf = gdf.reindex(catchment_ids)
    output_dir = 'output_plots'
    os.makedirs(output_dir, exist_ok=True)
    
    images = []
    for j, jtime in enumerate(t_ax):
        fig, axes = plt.subplots(1, 2, figsize=(8, 8), dpi=200)
        jfile=netcdf_files[j]
        ds = xr.open_dataset(jfile)
        units = ds[nwm_variable].units
        nwm_var = ds[nwm_variable].isel(x=slice(x_min, x_max + 1), y=slice(3840 - y_max, 3840 - y_min + 1))
        if j==0:
            cmin=np.min(nwm_var)
            cmax=np.max(nwm_var)
        nwm_var = np.flip(nwm_var[0,:,:], 0)
        im = axes[0].imshow(nwm_var, vmin=cmin, vmax=cmax)
        axes[0].axis('off')
        axes[0].set_title(f'NWM')

        gdf[ngen_variable] = ngen_data[:, j, var_idx]
        image = gdf.plot(
            column=ngen_variable,
            ax=axes[1],
            vmin=cmin, 
            vmax=cmax
            )
        axes[1].set_title(f'NGEN')
        axes[1].axis('off')
        fig_name = f'{jtime}.png'
        plt.colorbar(im, 
                    ax=axes,
                    orientation='horizontal', 
                    fraction=.1,
                    label=f'{nwm_variable} -> {ngen_variable} {units}'
                    )

        plt.suptitle(f"{domain} {t_ax[j]}")
        plt.savefig(os.path.join(output_dir, fig_name))
        plt.close()
        jpng = os.path.join(output_dir, fig_name)
        images.append(imageio.imread(jpng))
        os.remove(jpng)
    imageio.mimsave(os.path.join(output_dir, f'{nwm_variable}_2_{ngen_variable}.gif')mweq    , images, loop=0, fps=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ngen_folder", help="Path to a folder containing ngen catchment forcings",default="")
    parser.add_argument("--nwm_folder",  help="Path to a folder containing nwm CONUS forcings",default="")
    parser.add_argument("--weights_json",  help="Path to a file containing catchment indices relative to grids in nwm_folder",default="")
    parser.add_argument("--geopackage",  help="Path to a geopackage from which the weights were created",default="")
    args = parser.parse_args()

    print(f'Collecting data...')
    with open(args.weights_json, "r") as f:
        weights_json = json.load(f)

    nc_files = []
    for path, _, files in os.walk(args.nwm_folder):
        for jfile in files:
            jfile_path = os.path.join(path,jfile)
            nc_files.append(jfile_path)

    catchment_ids = []
    for (path, _, files) in os.walk(args.ngen_folder):        
        for j, jfile in enumerate(files):
            catchment_id = jfile.split('.')[0] 
            catchment_ids.append(catchment_id)
            ngen_jdf = pd.read_csv(os.path.join(args.ngen_folder, jfile))
            if j == 0: 
                t_ax = ngen_jdf['time']
                ngen_jdf = ngen_jdf.drop(columns='time')
                shp = ngen_jdf.shape
                ngen_data = np.zeros((len(files),shp[0],shp[1]),dtype=np.float32)
            else:
                ngen_jdf = ngen_jdf.drop(columns='time')
            ngen_data[j,:,:] = np.array(ngen_jdf)

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
    global x_min, x_max, y_min, y_max
    x_min=np.min(x_min_list)   
    x_max=np.max(x_max_list)   
    y_min=np.min(y_min_list)   
    y_max=np.max(y_max_list) 

    for j, j_ngen_var in enumerate(ngen_variables):
        j_nwm_var = nwm_variables[j]
        print(f'creating gif for variables {j_nwm_var} -> {j_ngen_var}')
        plot_ngen_forcings(sorted(nc_files), 
            args.geopackage, 
            ngen_data, t_ax, 
            catchment_ids,
            j_nwm_var, 
            j_ngen_var,
            j,
            'VPU 18'
            )
    print(f'Gifs creation complete')