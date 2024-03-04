import argparse, os
import json, re, copy

def generate_vpu_execs(conf,out_dir):
    if os.path.exists(out_dir):
        print(f'Delete {out_dir}')
        quit
    else:
        os.system(f"mkdir -p {out_dir}")

    with open(conf,"r") as fp:
        execution_template = json.load(fp)

    vpus = ["01","02","03N","03S","03W","04","05","06", "07","08","09",
            "10L","10U","11","12","13","14","15","16","17","18",]
    pattern = r'\$VPU'
    instance_name = execution_template['instance_parameters']['TagSpecifications'][0]['Tags'][0]['Value']
    for jvpu in vpus:
        exec_jvpu = copy.deepcopy(execution_template)
        exec_jvpu['instance_parameters']['TagSpecifications'][0]['Tags'][0]['Value'] = re.sub(pattern, jvpu, instance_name)
        stream_command = copy.deepcopy(exec_jvpu['commands'][2])
        exec_jvpu['commands'][2] = re.sub(pattern, jvpu, stream_command)
        out_file = os.path.join(out_dir,f"execution_dailyrun_{jvpu}.json")
        with open(out_file,'w') as fp:
            json.dump(exec_jvpu,fp,indent=2)
       
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exec_template", type=str, help="A statemachine execution json file for ngen-datastream")
    parser.add_argument("--out_dir", type=str, help="Path to write executions out to, must not exist")

    args    = parser.parse_args()
    conf    = args.exec_template
    out_dir = args.out_dir

    generate_vpu_execs(conf,out_dir)
