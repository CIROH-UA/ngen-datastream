import argparse

def generate_vpu_execs(conf,out_dir):
    pass



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exec_template", type=str, help="A statemachine execution json file for ngen-datastream")
    parser.add_argument("--out_dir", type=str, help="Path to write executions out to, must not exist")

    args    = parser.parse_args()
    conf    = args.exec_template
    out_dir = args.out_dir

    generate_vpu_execs(conf,out_dir)
