from forcingprocessor.weights_hf2ds import hf2ds
from pathlib import Path
import os
import time
import pytest

HF_VERSION="v2.1.1"
test_dir = Path(__file__).parent
data_dir = (test_dir/'data').resolve()
os.system(f'mkdir {data_dir}')
out_parq = os.path.join(data_dir,"out.parquet")
parq_name = "09_weights.parquet"
parq_path = os.path.join(data_dir,parq_name)
os.system(f"curl -o {parq_path} -L -O https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/{HF_VERSION}/nextgen/conus_forcing-weights/vpuid%3D09/part-0.parquet")
geopackage_name = "palisade.gpkg"
gpkg_path = os.path.join(data_dir,geopackage_name)
os.system(f"curl -o {gpkg_path} -L -O https://ngen-datastream.s3.us-east-2.amazonaws.com/{geopackage_name}")

def test_parquet():
    weights,_ = hf2ds([parq_path])
    assert len(weights) > 0

def test_parquet_lynker_spatial():
    weights,_ = hf2ds(["https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/v2.1.1/nextgen/conus_forcing-weights/vpuid%3D01/part-0.parquet"])
    assert len(weights) > 0    

def test_gpkg():
    weights,_ = hf2ds([gpkg_path])
    assert len(weights) > 0


