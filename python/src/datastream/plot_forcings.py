import xarray as xr
import argparse, os, json
import matplotlib as mpl
import matplotlib.pyplot as plt
import imageio.v2 as imageio
import numpy as np
import pandas as pd
import geopandas as gpd
mpl.use('Agg')

cmin=265
cmax=305

def plot_nwm_forcings(netcdf_files, variable='T2D', output_gif='nwm_output.gif'):

    frames = []
    for j, file in enumerate(sorted(netcdf_files)):
        ds = xr.open_dataset(file)
        T2D = ds['T2D'].isel(x=slice(x_min, x_max + 1 ), y=slice(3840 - y_max, 3840 - y_min + 1))
        T2D = np.flip(T2D[0,:,:], 0)
        fig = plt.figure(figsize=(6,6),dpi=200)
        im = plt.imshow(T2D, vmin=cmin, vmax=cmax)
        cb = fig.colorbar(im, orientation='horizontal')
        cb.set_label('Surface runoff (mm)')
        plt.title(f'NWM {variable} - {ds.model_output_valid_time}')
        filename = f'temp_plot_{j}.png'
        plt.savefig(filename)
        plt.close()
        frames.append(imageio.imread(filename))
        os.remove(filename)
        ds.close()
    imageio.mimsave(output_gif, frames, fps=2)

def plot_ngen_forcings(geopackage, ngen_data, t_ax, catchment_ids, variable='T2D', output_gif='ngen_output.gif'):    
    gdf = gpd.read_file(geopackage, layer='divides')
    gdf = gdf.set_index('divide_id')
    gdf = gdf.reindex(catchment_ids)
    output_dir = 'output_plots'
    os.makedirs(output_dir, exist_ok=True)
    images = []
    for j, jtime in enumerate(t_ax):
        plt.figure()
        gdf[variable] = ngen_data[:,j,5]
        gdf.plot(column=variable, legend=True,vmin=cmin, vmax=cmax)
        plt.title(f'NGEN {variable} - {t_ax[j]}')
        fig_name = f'{jtime}.png'
        plt.savefig(os.path.join(output_dir, fig_name))
        plt.tight_layout()
        plt.title(f"NWM {variable} Processed into NGEN")
        plt.close()
        jpng = os.path.join(output_dir, fig_name)
        images.append(imageio.imread(jpng))
        os.remove(jpng)
    imageio.mimsave(output_gif, images, fps=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ngen_folder", help="Path to a folder containing ngen catchment forcings",default="")
    parser.add_argument("--nwm_folder",  help="Path to a folder containing nwm CONUS forcings",default="")
    parser.add_argument("--weights_json",  help="Path to a file containing catchment indices relative to grids in nwm_folder",default="")
    parser.add_argument("--geopackage",  help="Path to a geopackage from which the weights were created",default="")
    args = parser.parse_args()

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

    plot_nwm_forcings(nc_files, variable='T2D', output_gif='T2D_nwm_18.gif')
    plot_ngen_forcings(args.geopackage, ngen_data, t_ax, catchment_ids, variable='TMP_2maboveground', output_gif='T2D_ngen_18.gif')
    print(f'Gifs creation complete')