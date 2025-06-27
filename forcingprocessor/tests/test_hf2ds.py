from forcingprocessor.weights_hf2ds import hf2ds, multiprocess_hf2ds
from pathlib import Path
import os

HF_VERSION="v2.1.1"
test_dir = Path(__file__).parent
data_dir = (test_dir/'data').resolve()
os.system(f'mkdir {data_dir}')
out_parq = os.path.join(data_dir,"out.parquet")
parq_name = "09_weights.parquet"
parq_path = os.path.join(data_dir,parq_name)

geopackage_name = "palisade.gpkg"
gpkg_path = os.path.join(data_dir,geopackage_name)
raster = "https://noaa-nwm-retrospective-3-0-pds.s3.amazonaws.com/CONUS/netcdf/FORCING/2018/201801010000.LDASIN_DOMAIN1"

def test_parquet_v21():
    os.system(f"curl -o {parq_path} -L -O https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/{HF_VERSION}/nextgen/conus_forcing-weights/vpuid%3D09/part-0.parquet")
    weights,_ = hf2ds([parq_path],raster,1)
    assert len(weights) > 0

def test_gpkg_v21():
    os.system(f"curl -o {gpkg_path} -L -O https://ngen-datastream.s3.us-east-2.amazonaws.com/{geopackage_name}")
    weights,_ = hf2ds([gpkg_path],raster,1)
    assert len(weights) > 0

def test_gpkg_v22():
    weights,_ = hf2ds(["https://communityhydrofabric.s3.us-east-1.amazonaws.com/hydrofabrics/community/VPU/vpu-09_subset.gpkg"],raster,1)
    assert len(weights) > 0


def test_multiple_parquet_v21():
    os.system(f"curl -o {parq_path} -L -O https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/{HF_VERSION}/nextgen/conus_forcing-weights/vpuid%3D09/part-0.parquet")
    weights,_ = hf2ds([parq_path,parq_path],raster,1)
    assert len(weights) > 0

def test_multiple_gpkg_v21():
    os.system(f"curl -o {gpkg_path} -L -O https://ngen-datastream.s3.us-east-2.amazonaws.com/{geopackage_name}")
    weights,_ = hf2ds([gpkg_path,gpkg_path],raster,1)
    assert len(weights) > 0

def test_multiple_gpkg_v22():
    weights,_ = hf2ds(["https://communityhydrofabric.s3.us-east-1.amazonaws.com/hydrofabrics/community/VPU/vpu-09_subset.gpkg","https://communityhydrofabric.s3.us-east-1.amazonaws.com/hydrofabrics/community/VPU/vpu-09_subset.gpkg"],raster,1)
    assert len(weights) > 0    

def test_multiple_multiprocess_parquet_v21():
    os.system(f"curl -o {parq_path} -L -O https://lynker-spatial.s3-us-west-2.amazonaws.com/hydrofabric/{HF_VERSION}/nextgen/conus_forcing-weights/vpuid%3D09/part-0.parquet")
    weights,_ = multiprocess_hf2ds([parq_path,parq_path],raster,2)
    assert len(weights) > 0

def test_multiple_multiprocess_gpkg_v21():
    os.system(f"curl -o {gpkg_path} -L -O https://ngen-datastream.s3.us-east-2.amazonaws.com/{geopackage_name}")
    weights,_ = multiprocess_hf2ds([gpkg_path,gpkg_path],raster,2)
    assert len(weights) > 0

def test_multiple_multiprocess_gpkg_v22():
    weights,_ = multiprocess_hf2ds(["https://communityhydrofabric.s3.us-east-1.amazonaws.com/hydrofabrics/community/VPU/vpu-09_subset.gpkg","https://communityhydrofabric.s3.us-east-1.amazonaws.com/hydrofabrics/community/VPU/vpu-09_subset.gpkg"],raster,2)
    assert len(weights) > 0       

