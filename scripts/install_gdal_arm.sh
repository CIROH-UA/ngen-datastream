#!/bin/bash

#https://repost.aws/articles/ARJV3lAJE0TcWZMrxqpQ5D3Q/installing-python-package-geopandas-on-amazon-linux-2023-for-graviton

dnf -y install gcc-c++ cpp sqlite-devel libtiff cmake python3-pip \
    python-devel openssl-devel tcl libtiff-devel libcurl-devel \
    swig libpng-devel libjpeg-turbo-devel expat-devel

wget https://download.osgeo.org/proj/proj-9.3.1.tar.gz
tar zxvf proj-9.3.1.tar.gz
cd proj-9.3.1/
mkdir build
cd build
cmake ..
cmake --build . --parallel $(nproc)
sudo cmake --install . --prefix /usr
cd ~

wget https://github.com/OSGeo/gdal/releases/download/v3.8.3/gdal-3.8.3.tar.gz
tar xvzf gdal-3.8.3.tar.gz
cd gdal-3.8.3/
mkdir build
cd build
cmake -DGDAL_BUILD_OPTIONAL_DRIVERS=OFF -DOGR_BUILD_OPTIONAL_DRIVERS=OFF ..
cmake --build . --parallel $(nproc)
sudo cmake --install . --prefix /usr
cd ~
