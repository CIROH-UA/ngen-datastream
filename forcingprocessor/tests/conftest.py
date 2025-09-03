import pytest, os

@pytest.fixture(scope="session")
def clean_s3_test():
    yield
    os.system("aws s3 rm s3://ciroh-community-ngen-datastream/test/nrds_fp_test/ --recursive")