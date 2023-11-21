import pytest, os
from pathlib import Path

from subsetting.subset import subset_upstream

geopkg_filename = "nextgen_01.gpkg"
geopkg_file     = f"https://ngenresourcesdev.s3.us-east-2.amazonaws.com/{geopkg_filename}"

@pytest.fixture()
def get_paths():
    test_dir = Path(__file__).parent
    data_dir = (test_dir/'data').resolve()
    pwd      = Path.cwd()
    pytest.pwd      = pwd
    pytest.data_dir = data_dir
    full_geo    = (data_dir/geopkg_filename).resolve()
    pytest.full_geo    = full_geo

@pytest.fixture()
def test_generate_weights(get_paths):
    geopkg_local = (pytest.data_dir/geopkg_filename).resolve()
    if not geopkg_local.exists(): 
        os.system(f'wget {geopkg_file} -P {pytest.data_dir}')    

def test_subset_upstream():
    cat_id = "cat-2975"

    subset_upstream(pytest.full_geo,cat_id)
    assert Path("./catchments.geojson").exists()
