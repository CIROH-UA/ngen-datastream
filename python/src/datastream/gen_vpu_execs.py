import argparse, os
import json, re, copy
import pandas as pd

def generate_vpu_execs(instance_types,conf,out_dir,arch,arch_file):
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
    for j,jvpu in enumerate(VPUs):
        exec_jvpu = copy.deepcopy(execution_template)
        exec_jvpu['instance_parameters']['ImageId'] = ami
        exec_jvpu['instance_parameters']['InstanceType'] = instance_types[j]
        exec_jvpu['instance_parameters']['TagSpecifications'][0]['Tags'][0]['Value'] = re.sub(pattern, jvpu, instance_name)
        stream_command = copy.deepcopy(exec_jvpu['commands'][2])
        exec_jvpu['commands'][2] = re.sub(pattern, jvpu, stream_command)
        out_file = os.path.join(out_dir,f"execution_dailyrun_{jvpu}.json")        
        with open(out_file,'w') as fp:
            json.dump(exec_jvpu,fp,indent=2)

def generate_vpu_sizes():
    file_str = "https://lynker-spatial.s3.amazonaws.com/v20.1/model_attributes/nextgen_$VPU.parquet"
    ncatchment_vpu = []
    for j,jvpu in enumerate(VPUs):
        data = pd.read_parquet(re.sub(pattern, jvpu, file_str))
        ncatchment = len(data)
        ncatchment_vpu.append(ncatchment)

    return ncatchment_vpu

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exec_template", type=str, help="A statemachine execution json file for ngen-datastream")
    parser.add_argument("--arch_file", type=str, help="Text file that holds the AMIs for each architecture")
    parser.add_argument("--arch", type=str, help="x86 or arm")
    parser.add_argument("--out_dir", type=str, help="Path to write executions out to, must not exist")

    args    = parser.parse_args()
    conf    = args.exec_template
    out_dir = args.out_dir
    arch_file = args.arch_file
    arch    = args.arch

    global VPUs, pattern
    pattern = r'\$VPU'
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

    ec2_types = []
    ec2_instance = 't2.'
    for jvpu in ncatchment_vpu:
        if jvpu > 60000:
            ec2_types.append(ec2_instance + '2xlarge')
        elif jvpu <= 60000 and jvpu > 30000:
            ec2_types.append(ec2_instance + '2xlarge') 
        elif jvpu <= 30000:
            ec2_types.append(ec2_instance + '2xlarge')

    generate_vpu_execs(ec2_types,conf,out_dir,arch,arch_file)


