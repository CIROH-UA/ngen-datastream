import argparse, os, datetime, json

class DatastreamValues:
    def __init__(self, ncatchments, datastream_conf):
        self.ncatchments = ncatchments
        self.nts         = datastream_conf['ncatchments'] 
        self.nprocs      = datastream_conf['globals']['nprocs']  
        self.host_type   = datastream_conf['host']['host_type']    
        self.host_cores  = datastream_conf['host']['host_cores']   
        self.host_RAM    = datastream_conf['host']['host_RAM']   

class DatastreamTimeChunk(DatastreamValues):

    def __init__(self, datastream_vals:DatastreamValues, start_time:datetime.datetime, end_time:datetime.datetime):
        self.start_time = start_time
        self.end_time   = end_time
        self.duration_s = start_time - start_time
        self.duration_per_catchment = self.ncatchments / self.duration_s

def collect_profile_data(vals, data_dir):
    pro_file = os.path.join(data_dir,"datastream-configs/profile.txt")
    with open(pro_file,'r') as fp:
        data = fp.readlines()

    chunks = {}
    for jline in data:
        parts = jline.split(": ")
        label = parts[0]
        if label not in chunks: chunks[label] = {}
        if "_START" in jline: 
            chunks[label]['start_time'] = datetime.datetime(parts[1])
        if "_END" in jline: 
            chunks[label]['end_time'] = datetime.datetime(parts[1])  

    datastream_chunks = []
    for jchunk in chunks:
        datastream_chunks.append(DatastreamTimeChunk(chunks[jchunk]["start_time"],chunks[jchunk]["end_time"]))

    return datastream_chunks

def collect_datastream_configuration(data_dir):
    conf_file = os.path.join(data_dir,"datastream-configs/conf_datastream.json")
    with open(conf_file,'r') as fp:
        data = json.load(fp)  

    forcing_dir = os.path.join(data_dir,"ngen-run/forcings/")
    ncatchments = len([name for name in os.listdir(forcing_dir) if os.path.isfile(name)]) - 1
    return DatastreamValues(ncatchments,conf_file)

def plot_runtime(profile):
    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ii_show_plot", type=str, help="Show plots",default=False)
    parser.add_argument("--datastream_dir", type=str, help="Path to ngen-datastream data path",required=True)
    args = parser.parse_args()

    data_path = args.datastream_dir

    vals = collect_datastream_configuration(data_path)
    chunks = collect_profile_data(vals, data_path)


