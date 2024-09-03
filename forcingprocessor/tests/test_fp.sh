#!/bin/bash

python -m pytest -vv --deselect="forcingprocessor/tests/test_forcingprocessor.py::test_google_cloud_storage" --deselect="forcingprocessor/tests/test_forcingprocessor.py::test_gcs" --deselect="forcingprocessor/tests/test_forcingprocessor.py::test_gs" --deselect="forcingprocessor/tests/test_forcingprocessor.py::test_ciroh_zarr" --deselect="forcingprocessor/tests/test_forcingprocessor.py::test_nomads_post_processed" --deselect="forcingprocessor/tests/test_forcingprocessor.py::test_retro_ciroh_zarr"
python -m pytest -v -k test_google_cloud_storage 
python -m pytest -v -k test_gs 
python -m pytest -v -k test_gcs 