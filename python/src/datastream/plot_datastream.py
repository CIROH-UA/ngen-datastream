import json, os, argparse
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import re
import copy
from scipy.stats import linregress

VPUs = ["01","02","03N",
    "03S","03W","04",
    "05","06", "07",
    "08","09","10L",
    "10U","11","12",
    "13","14","15",
    "16","17","18",]

ncatchment_vpu = [19194, 33779, 30052, 
                    13758, 30199, 34641, 
                    51118, 13888, 56704, 
                    32532, 10999, 54688, 
                    83963, 62781, 36413, 
                    25482, 32760, 39578, 
                    34201, 80040, 40803]  

PRICING_DICT={}
PRICING_DICT["t4g.2xlarge"]=0.2688

plt.switch_backend('Agg')
plt.style.use('dark_background')

def profile_txt2df(txt_file):
    with open(txt_file,'r') as fp:
        data = fp.readlines()

    out_dict = {}
    total = 0
    total_lite = 0
    for jline in data:
        jline_parts = jline.strip().split("_")
        jtime_stamp = datetime.strptime(jline_parts[-1].split(": ")[-1],'%Y%m%d%H%M%S')
        step = "_".join(jline_parts[:-1])
        if step == "DATASTREAM":continue
        if step not in out_dict.keys():
            out_dict[step] = {}
            out_dict[step]["start_time"] = jtime_stamp
            continue
        if step in out_dict.keys():
            out_dict[step]["end_time"] = jtime_stamp
            out_dict[step]["duration_seconds"] = (out_dict[step]["end_time"] - out_dict[step]["start_time"]).seconds
            if not np.isnan(out_dict[step]["duration_seconds"]): 
                total+=out_dict[step]["duration_seconds"]
                if step != "WEIGHTS" and step != "NGENCONFGEN":
                    total_lite+=out_dict[step]["duration_seconds"]


    out_dict_tmp = copy.deepcopy(out_dict)
    for jstep in out_dict_tmp:
        if "end_time" not in out_dict[jstep]: out_dict.pop(jstep)

    out_dict_lite = copy.deepcopy(out_dict)
    out_dict_lite.pop("WEIGHTS")
    out_dict_lite.pop("NGENCONFGEN")

    out_dict["total_runtime"] = total
    out_dict_lite["total_runtime"] = total_lite
    pro_df = pd.DataFrame.from_dict(out_dict)
    pro_df_lite = pd.DataFrame.from_dict(out_dict_lite)

    return pro_df, pro_df_lite

def get_steps_dict(profile_dict):
  
    step_dfs = {}
    VPU_list = []
    ncatchment_list = []
    steps = None
    for jpro in profile_dict:
        profile_name = jpro
        for j,jVPU in enumerate(VPUs):
            if jVPU in profile_dict[jpro]["file_name"]:
                VPU_list.append(jVPU)
                ncatchment_list.append(ncatchment_vpu[j])

        jdf = profile_dict[jpro]["profile_df"]
        if steps is None: steps = jdf.columns
        for j, jstep in enumerate(steps):
            jstep_duration = jdf[jstep]["duration_seconds"]/60
            
            if jstep not in step_dfs:
                step_dfs[jstep] = pd.DataFrame({"profile":[profile_name],"duration_minutes":[jstep_duration]})
            else:
                step_dfs[jstep] = pd.concat([pd.DataFrame({"profile":[profile_name],"duration_minutes":[jstep_duration]}),step_dfs[jstep]],ignore_index=True)
    return step_dfs, ncatchment_list

def plot_group(profile_dict, profile_dict_lite,conf_dict,input_csv):
    
    
    step_dfs, ncatchment_list = get_steps_dict(profile_dict)
    step_dfs_lite, _          = get_steps_dict(profile_dict_lite)

    profile_list = []
    for jrow in step_dfs["GET_RESOURCES"]["profile"]:
        profile_list.append(jrow.split("_")[-1])

    order = []
    for jVPU in profile_list:
        for k,kVPU in enumerate(VPUs):
            if jVPU == kVPU:
                order.append(k)

    order = np.argsort(np.array(ncatchment_vpu)[order])
        
    step_dfs_sorted          = {}
    step_dfs_proportion      = {}
    step_dfs_lite_sorted     = {}
    step_dfs_lite_proportion = {}
    for jdf in step_dfs:
        step_dfs_sorted[jdf]          = step_dfs[jdf].reindex(order)        
        step_dfs_proportion[jdf]      = step_dfs[jdf].reindex(order)
        if jdf != "WEIGHTS" and jdf != "NGENCONFGEN":
            step_dfs_lite_sorted[jdf]     = step_dfs_lite[jdf].reindex(order)
            step_dfs_lite_proportion[jdf] = step_dfs_lite[jdf].reindex(order)
        if jdf != "total_runtime": 
            step_dfs_proportion[jdf]["proportion"] = 100 * (step_dfs[jdf]["duration_minutes"].reindex(order) / step_dfs["total_runtime"]["duration_minutes"].reindex(order))
            if jdf != "WEIGHTS" and jdf != "NGENCONFGEN":
                step_dfs_lite_proportion[jdf]["proportion"] = 100 * (step_dfs_lite[jdf]["duration_minutes"].reindex(order) / step_dfs_lite["total_runtime"]["duration_minutes"].reindex(order))
        step_dfs_proportion[jdf] = step_dfs_proportion[jdf].drop(columns="duration_minutes")
        if jdf != "WEIGHTS" and jdf != "NGENCONFGEN": 
            step_dfs_lite_proportion[jdf] = step_dfs_lite_proportion[jdf].drop(columns="duration_minutes")

    plot_cost_chart(step_dfs_sorted,step_dfs_lite_sorted,conf_dict)

    for jrun in conf_dict:
        host = conf_dict[jrun]["host"]
        nprocs = conf_dict[jrun]['globals']['nprocs']
        cores = host["host_cores"]
        ram = host["host_RAM"]
        host_type = host["host_type"].split(": ")[-1]
        host_type = "t4g.2xlarge"
        cost_per_hr = PRICING_DICT[host_type]
        host_arch = host["host_arch"]
        add_text  = "Run Info\n"        
        add_text += f"cores:    {cores}\n"
        add_text += f"nprocs:  {nprocs}\n"
        add_text += f"RAM:     {ram}\n"
        add_text += f"type:     t4g.2xlarge\n"
        add_text += f"arch:     {host_arch}\n"

    ncatchment_list_sorted = sorted(np.array(ncatchment_list))
    vpu_n_catchments = []
    for j, jcatch in enumerate(ncatchment_list_sorted):
        idx = np.where(jcatch == ncatchment_vpu)[0][0]
        vpu_n_catchments.append(f"{jcatch}, {VPUs[idx]}")

    write_to_csv(input_csv,ncatchment_list_sorted,step_dfs_lite_sorted,"duration_minutes",conf_dict,cost_per_hr)

    step_dfs_sorted.pop("total_runtime")
    step_dfs_proportion.pop("total_runtime")
    step_dfs_lite_sorted.pop("total_runtime")
    step_dfs_lite_proportion.pop("total_runtime")

    colors_lite = ['red', "blueviolet",         "cyan", "green",         "orange", 'indigo', "magenta","lime"]  
    colors      = ['red', "blueviolet", 'blue', "cyan", "green", "teal", "orange", 'indigo', "magenta","lime"]    
    plot_bar_chart(ncatchment_list_sorted,step_dfs_proportion,"ngen-datastream profiling",'profile_vpu_propotions.png','Proportion Total Runtime','proportion',add_text,colors)
    plot_bar_chart(ncatchment_list_sorted,step_dfs_sorted,"ngen-datastream profiling",'profile_vpu.png',"Minutes",'duration_minutes',add_text,colors)
    plot_bar_chart(ncatchment_list_sorted,step_dfs_lite_sorted,"ngen-datastream-lite profiling",'profile_vpu_lite.png',"Minutes",'duration_minutes',add_text,colors_lite)
    plot_bar_chart(ncatchment_list_sorted,step_dfs_lite_proportion,"ngen-datastream-lite profiling",'profile_vpu_lite_propotions.png','Proportion Total Runtime','proportion',add_text,colors_lite)

    plot_scaling(ncatchment_list_sorted,step_dfs_sorted,"ngen-datastream scaling",'scaling_vpu.png','Minutes','duration_minutes',add_text,colors)
    # write_to_csv(ncatchment_list_sorted,step_dfs_sorted)

# def plot_cost():
#     plt.clf()
#     combined_df = pd.concat(dfs.values(), keys=dfs.keys())
#     combined_df = combined_df.unstack(level=0)
#     legend_entries = []
#     fig, ax = plt.subplots()
#     for j,jcol in enumerate(combined_df[key].columns):
#         ax.plot(xticklabelz,combined_df[key][jcol],label=jcol,color=colors[j])

#     pass    

def write_to_csv(benchmark,catchments,dfs,key,confs,cost_per_hr):  
    steps = list(dfs.keys())
    benchmark_df = pd.read_csv(benchmark, index_col="Run ID")
    combined_df = pd.concat(dfs.values(), keys=dfs.keys())

    nts = 24
    idx = np.where(~np.isnan(benchmark_df.index))[0][-1]
    last = benchmark_df.index[idx]

    idx_combo = combined_df['profile']['total_runtime'].index

    df_append = []
    for j, jprofile in enumerate(dfs['GET_RESOURCES'].profile):
        jrun = jprofile.split("profile_")[-1]
        runtime_min = dfs['total_runtime'].set_index('profile')['duration_minutes'][jprofile]
        jdict = {}
        jdict["Run ID"]        = last + j
        jdict["Provider"]      = "AWS"
        # jdict["Instance Type"] = confs[jrun]['host']['host_type']
        jdict["Instance Type"] = "t4g.2xlarge"
        jdict["Cores"]         = confs[jrun]['host']['host_cores']
        # jdict["Memory (GB)"]        = confs[jrun]['host']['host_RAM']
        jdict["Memory (GB)"]        = 32
        jdict["Hardware"]      = confs[jrun]['host']['host_arch']
        # jdict["OS"]            = confs[jrun]['host']['host_os']
        jdict["OS"]            = "AWS Linux 2023"
        jdict["Cost/hr"]       = f"${cost_per_hr}"
        # jdict["Domain Name"]   = confs[jrun]['globals']['domain_name']
        jdict["Domain Name"]   = f"nextgen_{jrun}"
        jdict["Catchments"]    = catchments[j]
        jdict["Realization"]   = "CFE, PET, SLOTH, NOM"
        for jstep in steps:
            jdict[f"{jstep} Yearly Cost"] = 365 * combined_df['duration_minutes'][jstep][idx_combo[j]] * cost_per_hr / 60
        jdict["Total Runtime (minutes)"]           = runtime_min
        jdict["Catchments/core/timestep/second"]   = catchments[j] / confs[jrun]['host']['host_cores'] / nts / (runtime_min / 60)
        jdict["CONUS equivalent concurrent vCPUs"] = len(ncatchment_vpu) * confs[jrun]['host']['host_cores']
        jdict["Daily Operating Cost"]              = (runtime_min/60) * cost_per_hr 
        jdict["Yearly Operating Cost"]       = 365 * (runtime_min/60) * cost_per_hr 
        jdict["Daily Operating Cost/Timestep"]     = (runtime_min/60) * cost_per_hr / nts
        df_append.append(jdict)
        
    df_append = pd.DataFrame(df_append).set_index("Run ID")
    df_old = benchmark_df.drop(benchmark_df.index[np.arange(idx,len(benchmark_df))])

    benchmark_name = os.path.basename(benchmark).split('.csv')[0]
    today = datetime.now().strftime("%Y%m%d")
    benchmark_out  = os.path.join(os.path.dirname(benchmark),f"{benchmark_name}_{today}.xlsx")
    with pd.ExcelWriter(benchmark_out) as writer: 
        df_append.to_excel(writer,sheet_name=confs[jrun]['host']['host_type'].split(": ")[-1])
        df_old.to_excel(writer,sheet_name="Old Runs")

    pass  

def plot_scaling(xticklabelz,dfs,title,save_name,y_label,key,add_text,colors):
    plt.clf()
    combined_df = pd.concat(dfs.values(), keys=dfs.keys())
    combined_df = combined_df.unstack(level=0)
    legend_entries = []
    fig, ax = plt.subplots()
    for j,jcol in enumerate(combined_df[key].columns):
        ax.plot(xticklabelz,combined_df[key][jcol],label=jcol,color=colors[j])

        slope, intercept, r_value, p_value, std_err = linregress(xticklabelz, combined_df[key][jcol])
        r_squared = r_value ** 2
        legend_entry = f"{jcol} ({10000*slope:.2f}, {r_squared:.2f})"
        legend_entries.append(legend_entry)        

    plt.legend(legend_entries,fontsize='small', title='(slope 10k catchments/minute), R^2', bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.xlabel('Number of catchments')
    plt.ylabel(y_label)
    
    plt.grid(True, which='both', axis='both')
    plt.text(1.1, 0.07, add_text, transform=ax.transAxes, ha='left', va='bottom', fontsize=10, color='black')
    
    plt.subplots_adjust(right=0.52)

    plt.title(title)
    plt.savefig(os.path.join(out_dir,save_name))
    
def plot_cost_chart(dfs,dfs_lite,confs):


    pass

def plot_bar_chart(xticklabelz,dfs,title,save_name,y_label,key,add_text,colors):    
    combined_df = pd.concat(dfs.values(), keys=dfs.keys())
    combined_df = combined_df.unstack(level=0)
    ax = combined_df.plot(kind='bar', stacked=True, zorder=2,color=colors)

    ax.set_xticks(np.arange(len(combined_df.index)))
    ax.set_xticklabels(xticklabelz, rotation=45)

    plt.xlabel('Number of catchments')
    plt.ylabel(y_label)
    plt.legend(list(dfs.keys()), fontsize='small', title='steps', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True, which='both', axis='both', zorder=1)
    plt.text(1.1, -0.05, add_text, transform=ax.transAxes, ha='left', va='bottom', fontsize=10, color='black')

    plt.subplots_adjust(right=0.65)
    plt.subplots_adjust(bottom=0.2)

    plt.title(title)
    plt.savefig(os.path.join(out_dir,save_name))
    plt.clf()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", help="Path to directory holding many datastream-configs/",default=None)
    parser.add_argument("--out_dir", help="plot output directory",default=None)
    parser.add_argument("--input_csv", help="benchmark csv",default=None)
    args = parser.parse_args()

    global out_dir
    out_dir = args.out_dir

    input_csv = args.input_csv
    data_dir = args.data_dir
    all_profiles = {}
    all_profiles_lite = {}
    all_confs = {}
    for path, _, files in os.walk(data_dir):
        for jfile in files:
            jfile_path = os.path.join(path,jfile)
            jname = jfile.split(".")[0]
            pattern = r"profile_.*\.txt"
            if re.search(pattern,jfile_path):    
                jfile_df, jfile_df_lite = profile_txt2df(jfile_path)
                all_profiles[jname] = {}
                all_profiles[jname]["file_name"] = jfile_path
                all_profiles[jname]["profile_df"] = jfile_df

                all_profiles_lite[jname] = {}
                all_profiles_lite[jname]["file_name"] = jfile_path
                all_profiles_lite[jname]["profile_df"] = jfile_df_lite

            pattern = r"conf_datastream.*\.json"
            if re.search(pattern,jfile_path):
                jname = jname.split("_")[2:][0]
                with open(jfile_path,'r') as fp:
                    all_confs[jname] = json.load(fp)

    plot_group(all_profiles,all_profiles_lite,all_confs,input_csv)