import os    

def get_files_in_dir(file_patterns,dir):
    realization_file = None
    noah_owp = None
    ngen_yaml = None
    out_list = [{x:None} for x in file_patterns]
    for path, _, files in os.walk(dir):
        for jfile in files:
            jfile_path = os.path.join(path,jfile)
            for jpattern in 
            if jfile_path.find('realization') >= 0: 
                realization_file = jfile_path
            if jfile_path.find('namelist.input') >= 0: 
                noah_owp = jfile_path
            if jfile_path.find('ngen.yaml') >= 0: 
                ngen_yaml = jfile_path