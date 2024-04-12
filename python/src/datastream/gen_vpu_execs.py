import argparse, os
import json, re, copy
import pandas as pd
from datetime import datetime

def edit_dict(execution_template,ami,instance_type,jvpu,instance_name,daily_date):
    exec_jvpu = copy.deepcopy(execution_template)
    exec_jvpu['instance_parameters']['ImageId'] = ami
    exec_jvpu['instance_parameters']['InstanceType'] = instance_type
    exec_jvpu['instance_parameters']['TagSpecifications'][0]['Tags'][0]['Value'] = re.sub(pattern_vpu, jvpu, instance_name)
    for j,jcmd in enumerate(exec_jvpu['commands']):
        stream_command = copy.deepcopy(jcmd)
        exec_jvpu['commands'][j] = re.sub(pattern_vpu, jvpu, stream_command)
        stream_command = copy.deepcopy(exec_jvpu['commands'][j])
        exec_jvpu['commands'][j] = re.sub(pattern_date, daily_date, stream_command)  
        stream_command = copy.deepcopy(exec_jvpu['commands'][j])      
        exec_jvpu['commands'][j] = re.sub(pattern_instance, instance_type, stream_command)     
    stream_command = copy.deepcopy(exec_jvpu['obj_key'])
    exec_jvpu['obj_key'] = re.sub(pattern_vpu, jvpu, stream_command)
    stream_command = copy.deepcopy(exec_jvpu['obj_key'])
    exec_jvpu['obj_key'] = re.sub(pattern_date, daily_date, stream_command)        
    stream_command = copy.deepcopy(exec_jvpu['obj_key'])
    exec_jvpu['obj_key'] = re.sub(pattern_instance, instance_type, stream_command)                
    out_file = os.path.join(out_dir,f"execution_dailyrun_{jvpu}.json")        
    with open(out_file,'w') as fp:
        json.dump(exec_jvpu,fp,indent=2)

def generate_vpu_execs(instance_types,conf,conf_fp,out_dir,arch,arch_file):
    if os.path.exists(out_dir):
        print(f'Delete {out_dir}')
        quit
    else:
        os.system(f"mkdir -p {out_dir}")

    with open(conf,"r") as fp:
        execution_template = json.load(fp)

    with open(arch_file,"r") as fp:
        [x86_ami,arm_ami]  = fp.readlines()
        if arch == "x86":   
            ami = x86_ami.strip()            
        elif arch == "arm": 
            ami = arm_ami.strip()
        ami = ami.replace(f'{arch}: ','')

    instance_name = execution_template['instance_parameters']['TagSpecifications'][0]['Tags'][0]['Value']
    daily_date = datetime.now()
    daily_date = daily_date.strftime('%Y%m%d')  
      
    for jvpu in VPUs:
        exec_jvpu = copy.deepcopy(execution_template)
        edit_dict(exec_jvpu,ami,instance_types[jvpu],jvpu,instance_name,daily_date)

    instance_type_fp = 'c7g.8xlarge'
    if conf_fp:
        with open(conf_fp,"r") as fp:
            execution_template = json.load(fp)
        instance_name = execution_template['instance_parameters']['TagSpecifications'][0]['Tags'][0]['Value']
        edit_dict(execution_template,ami,instance_type_fp,'fp',instance_name,daily_date)    
               

def generate_vpu_sizes():
    file_str = "https://lynker-spatial.s3.amazonaws.com/v20.1/model_attributes/nextgen_$VPU.parquet"
    ncatchment_vpu = []
    for j,jvpu in enumerate(VPUs):
        data = pd.read_parquet(re.sub(pattern_vpu, jvpu, file_str))
        ncatchment = len(data)
        ncatchment_vpu.append(ncatchment)

    return ncatchment_vpu

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exec_template_fp", type=str, help="A statemachine execution json file for ngen-datastream forcingprocessor")
    parser.add_argument("--exec_template_vpu", type=str, help="A statemachine execution json file for ngen-datastream")
    parser.add_argument("--ami_file", type=str, help="Text file that holds the AMIs for each architecture")
    parser.add_argument("--arch", type=str, help="x86 or arm")
    parser.add_argument("--out_dir", type=str, help="Path to write executions out to, must not exist")

    args      = parser.parse_args()
    conf_vpu  = args.exec_template_vpu
    conf_fp   = args.exec_template_fp
    out_dir   = args.out_dir
    ami_file  = args.ami_file
    arch      = args.arch

    global VPUs, pattern_vpu, pattern_date
    pattern_vpu = r'\$VPU'
    pattern_date = r'\$DATE'
    pattern_instance = r'\$INSTANCE_TYPE'
    VPUs = ["01","02","03N",
            "03S","03W","04",
            "05","06", "07",
            "08","09","10L",
            "10U","11","12",
            "13","14","15",
            "16","17","18",]

    # ncatchment_vpu = generate_vpu_sizes()
    ncatchment_vpu = [19194, 33779, 30052, 
                      13758, 30199, 34641, 
                      51118, 13888, 56704, 
                      32532, 10999, 54688, 
                      83963, 62781, 36413, 
                      25482, 32760, 39578, 
                      34201, 80040, 40803]

    # ec2_types = {
    #     "01":'t4g.xlarge',
    #     "02":'t4g.xlarge',
    #     "03N":'t4g.xlarge',
    #     "03S":'t4g.xlarge',
    #     "03W":'t4g.xlarge',
    #     "04":'t4g.xlarge',
    #     "05":'t4g.xlarge',
    #     "06":'t4g.xlarge',
    #     "07":'t4g.xlarge',
    #     "08":'t4g.xlarge',
    #     "09":'t4g.xlarge',
    #     "10L":'t4g.xlarge',
    #     "10U":'t4g.xlarge',
    #     "11":'t4g.xlarge',
    #     "12":'t4g.xlarge',
    #     "13":'t4g.xlarge',
    #     "14":'t4g.xlarge',
    #     "15":'t4g.xlarge',
    #     "16":'t4g.xlarge',
    #     "17":'t4g.xlarge',
    #     "18":'t4g.xlarge'
    # }

    ec2_types = {
        "01":'t4g.2xlarge',
        "02":'t4g.2xlarge',
        "03N":'t4g.2xlarge',
        "03S":'t4g.2xlarge',
        "03W":'t4g.2xlarge',
        "04":'t4g.2xlarge',
        "05":'t4g.2xlarge',
        "06":'t4g.2xlarge',
        "07":'t4g.2xlarge',
        "08":'t4g.2xlarge',
        "09":'t4g.2xlarge',
        "10L":'t4g.2xlarge',
        "10U":'t4g.2xlarge',
        "11":'t4g.2xlarge',
        "12":'t4g.2xlarge',
        "13":'t4g.2xlarge',
        "14":'t4g.2xlarge',
        "15":'t4g.2xlarge',
        "16":'t4g.2xlarge',
        "17":'t4g.2xlarge',
        "18":'t4g.2xlarge'
    }    

    generate_vpu_execs(ec2_types,conf_vpu,conf_fp,out_dir,arch,ami_file)

