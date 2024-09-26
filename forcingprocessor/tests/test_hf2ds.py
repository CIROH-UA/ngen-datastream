from forcingprocessor.weights_hf2ds import hf2ds
from pathlib import Path
import os
import pandas as pd

HF_VERSION="v2.1.1"
test_dir = Path(__file__).parent
data_dir = (test_dir/'data').resolve()
parq_name = "09_weights.parquet"
parq_path = os.path.join(data_dir,parq_name)
os.system(f"curl -o {parq_path} -L -O https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/{HF_VERSION}/nextgen/conus_forcing-weights/vpuid%3D09/part-0.parquet")
geopackage_name = "palisade.gpkg"
gpkg_path = os.path.join(data_dir,geopackage_name)
os.system(f"curl -o {gpkg_path} -L -O https://ngen-datastream.s3.us-east-2.amazonaws.com/{geopackage_name}")
out_parq = os.path.join(data_dir,"out.parquet")

def test_parquet():
    weights,_ = hf2ds([parq_path])
    assert len(weights) > 0

def test_gpkg():
    weights,_ = hf2ds([gpkg_path])
    assert len(weights) > 0

    weights_prep = []
    for jweight in weights:
        cell = weights[jweight][0]
        cov  = weights[jweight][1]
        jdict = {}
        jdict['divide_id'] = jweight
        jdict['cell'] = cell
        jdict['coverage_fraction'] = cov
        weights_prep.append(jdict)

    df = pd.DataFrame.from_records(weights_prep)
    df.to_parquet(out_parq)    

def test_ds_parquet():
    weights,_ = hf2ds([out_parq])
    assert len(weights) > 0


