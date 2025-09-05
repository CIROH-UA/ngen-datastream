#####
#
# gen_vpu_execs.py : a script to generate execution json files for the NextGen Research DataStream
# Author: Jordan J. Laser
# Email: jlaser@lynker.com
#
#####

import argparse, os
import json, re, copy
import pandas as pd
import boto3

VPU_NAMES = ["01","02","03N",
        "03S","03W","04",
        "05","06", "07",
        "08","09","10L",
        "10U","11","12",
        "13","14","15",
        "16","17","18",]

PATTERN_VPU = r'\$VPU'
PATTERN_INSTANCE = r'\$INSTANCE_TYPE'
PATTERN_NPROCS = r'\$NPROCS'
PATTERN_RUN_TYPE_H = r'\$RUN_TYPE_H'
PATTERN_RUN_TYPE_L = r'\$RUN_TYPE_L'
PATTERN_FCST = r'\$FCST'
PATTERN_INIT = r'\$INIT'
PATTERN_MEMBER = r'\$MEMBER'

PATTERN_FORECAST={
    "short_range"  : "f001_f018",
    "medium_range" : "f001_f240",
    "analysis_assim_extend"  : "tm27_tm00",
}

TIMEOUTS={    
    "short_range"  : 3600,
    "medium_range" : 7200,
    "analysis_assim_extend"  : 3600
    }

def get_ncores_from_instance_type(instance_type, cache_file):
    """
    Gets the number of vCPUs for a given EC2 instance type, using a cache to avoid unnecessary AWS calls.

    Args:
        instance_type (str): The EC2 instance type (e.g., "t2g.2xlarge").
        cache_file (str): Path to the JSON file used for caching instance type -> vCPU mappings.

    Returns:
        int: The number of vCPUs for the instance type, or 0 if not found.
    """
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cache = json.load(f)
        except json.JSONDecodeError:
            cache = {}
    else:
        cache = {}

    if instance_type in cache:
        return cache[instance_type]

    ec2_client = boto3.client('ec2')
    try:
        response = ec2_client.describe_instance_types(InstanceTypes=[instance_type])
        vcpus = response['InstanceTypes'][0]['VCpuInfo']['DefaultVCpus']
        cache[instance_type] = vcpus
        with open(cache_file, 'w') as f:
            json.dump(cache, f, indent=2)
        return vcpus
    except Exception as e:
        print(f"Error fetching instance type details: {e}")
        return 0
    
def remove_left_n_chars(text, pattern, n):
    matches = list(re.finditer(pattern, text))
    if not matches:
        return text

    # Work from right to left to avoid index shifting
    for match in reversed(matches):
        start_index = match.start()
        slice_start = max(0, start_index - n)
        text = text[:slice_start] + text[start_index:]

    return text

def edit_dict(execution_template,ami,instance_type,jvpu,out_dir,run_type,init,member,volume_size):
    cache_file = os.path.join(out_dir,"instance_type_cache.json")
    nprocs = get_ncores_from_instance_type(instance_type,cache_file)
    exec_jvpu = copy.deepcopy(execution_template)
    exec_jvpu['run_options']['timeout_s'] = TIMEOUTS[run_type]
    exec_jvpu['instance_parameters']['ImageId'] = ami
    exec_jvpu['instance_parameters']['InstanceType'] = instance_type
    exec_jvpu['instance_parameters']['BlockDeviceMappings'][0]['Ebs']['VolumeSize'] = volume_size
    instance_name = copy.deepcopy(exec_jvpu['instance_parameters']['TagSpecifications'][0]['Tags'][0]['Value'])
    exec_jvpu['instance_parameters']['TagSpecifications'][0]['Tags'][0]['Value'] = re.sub(PATTERN_VPU, jvpu, instance_name)
    instance_name = copy.deepcopy(exec_jvpu['instance_parameters']['TagSpecifications'][0]['Tags'][0]['Value'])
    exec_jvpu['instance_parameters']['TagSpecifications'][0]['Tags'][0]['Value'] = re.sub(PATTERN_RUN_TYPE_L, run_type.lower(), instance_name)
    if "datastream_command_options" in exec_jvpu.keys():
        key = "datastream_command_options"
        cmds = copy.deepcopy(exec_jvpu[key])
        cmds = [value for key, value in cmds.items()]
    else:
        key ="commands"
        cmds = copy.deepcopy(exec_jvpu[key])
    for j,jcmd in enumerate(cmds):
        stream_command = copy.deepcopy(jcmd)
        cmds[j] = re.sub(PATTERN_VPU, jvpu, stream_command)
        stream_command = copy.deepcopy(cmds[j])    
        cmds[j] = re.sub(PATTERN_NPROCS, str(nprocs - 1), stream_command)
        stream_command = copy.deepcopy(cmds[j])           
        cmds[j] = re.sub(PATTERN_INSTANCE, instance_type, stream_command)     
        stream_command = copy.deepcopy(cmds[j])      
        cmds[j] = re.sub(PATTERN_RUN_TYPE_H, run_type.upper(), stream_command)   
        stream_command = copy.deepcopy(cmds[j])      
        cmds[j] = re.sub(PATTERN_RUN_TYPE_L, run_type.lower(), stream_command) 
        stream_command = copy.deepcopy(cmds[j])      
        cmds[j] = re.sub(PATTERN_FCST, PATTERN_FORECAST[run_type.lower()], stream_command) 
        stream_command = copy.deepcopy(cmds[j])      
        cmds[j] = re.sub(PATTERN_INIT, init, stream_command)   
        stream_command = copy.deepcopy(cmds[j])
        if member == "":
            stream_command = remove_left_n_chars(stream_command, PATTERN_MEMBER, 1)     
        cmds[j] = re.sub(PATTERN_MEMBER, member, stream_command)

    # HACK
    # Edit whole path realization if medium range and vpu is 17
    # https://raw.githubusercontent.com/CIROH-UA/ngen-datastream/refs/heads/main/configs/ngen/realization_sloth_nom_cfe_pet.json
    if jvpu == "17":
        for j, jcmd in enumerate(cmds):
            stream_command = copy.deepcopy(jcmd)
            cmds[j] = re.sub(
                r'https://ciroh-community-ngen-datastream\.s3\.amazonaws\.com/realizations/realization_VPU_[0-9]{2}[A-Z]?\.json',
                'https://raw.githubusercontent.com/CIROH-UA/ngen-datastream/refs/heads/main/configs/ngen/realization_sloth_nom_cfe_pet.json',
                stream_command
            )
    # HACK
    # edit ens to zero for forcing source NWM_V3_MEDIUM_RANGE_<00,06,12, or 18>_X 
    # when ens member is 0 and jvpu is fp
    if run_type == "medium_range" and member == "1" and jvpu == "fp":
        for j, jcmd in enumerate(cmds):
            stream_command = copy.deepcopy(jcmd)
            cmds[j] = re.sub(
                r'NWM_V3_MEDIUM_RANGE_(00|06|12|18)_[0-9]+',
                r'NWM_V3_MEDIUM_RANGE_\1_0',
                stream_command
            )

    if "datastream_command_options" in exec_jvpu.keys():
        exec_jvpu[key] = dict([[key, value] for key, value in zip(exec_jvpu[key].keys(), cmds)])
    else:
        exec_jvpu[key] = cmds
    run_type_dir = os.path.join(out_dir,run_type)    
    if not os.path.exists(run_type_dir):
        os.makedirs(run_type_dir)
    if member == "":
        out_subdir = os.path.join(run_type_dir,init)
    else:
        out_subdir = os.path.join(run_type_dir,init,member)
    out_file = os.path.join(out_subdir,f"execution_datastream_{jvpu}.json")
    if not os.path.exists(out_subdir):
        os.makedirs(out_subdir)
    with open(out_file,'w') as fp:
        json.dump(exec_jvpu,fp,indent=2)

def generate_vpu_execs(inputs,conf,conf_fp,out_dir,arch,arch_file):

    with open(arch_file,"r") as fp:
        [x86_ami,arm_ami]  = fp.readlines()
        if arch == "x86":   
            ami = x86_ami.strip()            
        elif arch == "arm": 
            ami = arm_ami.strip()
        ami = ami.replace(f'{arch}: ','')        

    run_types = list(inputs.keys())

    for jrun in run_types:
        members = [""]
        jinits_jrun = inputs[jrun]['init_cycles']
        instance_types = inputs[jrun]['instance_types']
        volume_size = inputs[jrun]['volume_size']
        if jrun == "medium_range": 
            members = inputs[jrun]['ensemble_members']
        for jinit in jinits_jrun:
            for jmember in members:
                for jvpu in list(instance_types):
                    if jvpu != "fp":
                        with open(conf,"r") as fp:
                            execution_template = json.load(fp)
                        exec_jvpu = copy.deepcopy(execution_template)
                        edit_dict(exec_jvpu,ami,instance_types[jvpu],jvpu,out_dir,jrun,jinit,jmember,volume_size)
                    else:
                        if not conf_fp is None:
                            if len(members) > 1 and int(jmember) > 1 and jvpu == "fp":
                                # don't need to do forcings processing for members other than the first
                                continue
                            instance_type_fp = instance_types['fp']
                            with open(conf_fp,"r") as fp:
                                execution_template = json.load(fp)
                            edit_dict(execution_template,ami,instance_type_fp,'fp',out_dir,jrun,jinit,jmember,volume_size)    
               

def generate_vpu_sizes():
    file_str = "https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/v2.1.1/nextgen/conus_divides/vpuid%3D$VPU/part-0.parquet"
    ncatchment_vpu = []
    for j,jvpu in enumerate(VPU_NAMES):
        print(f'reading catchment data for {jvpu}')
        data = pd.read_parquet(re.sub(PATTERN_VPU, jvpu, file_str))
        ncatchment = len(data.divide_id)
        ncatchment_vpu.append(ncatchment)
        print(f'{ncatchment} catchments are in {jvpu}')
    return ncatchment_vpu

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exec_template_fp", default=None, type=str, help="A statemachine execution json file for ngen-datastream forcingprocessor")
    parser.add_argument("--exec_template_vpu", type=str, help="A statemachine execution json file for ngen-datastream")
    parser.add_argument("--ami_file", type=str, help="Text file that holds the AMIs for each architecture")
    parser.add_argument("--arch", type=str, help="x86 or arm")
    parser.add_argument("--inputs", type=str, help="json that holds inputs for each run type")
    parser.add_argument("--out_dir", type=str, help="Path to write executions out to, must not exist")

    args      = parser.parse_args()
    conf_vpu  = args.exec_template_vpu
    conf_fp   = args.exec_template_fp
    out_dir   = args.out_dir
    ami_file  = args.ami_file
    inputs    = args.inputs
    arch      = args.arch

    with open(inputs,"r") as fp:
        inputs = json.load(fp)

    generate_vpu_execs(inputs,conf_vpu,conf_fp,out_dir,arch,ami_file)

