ARG FUNCTION_DIR="/ngen-datastream"
FROM amazonlinux:2023 as build-image

ARG FUNCTION_DIR

RUN dnf -y install pigz tar git

RUN if [[ "$(uname -m)" == "aarch64" ]]; then \
        dnf -y install wget gcc-c++ cpp sqlite-devel libtiff cmake python3-pip \
            python-devel openssl-devel tcl libtiff-devel libcurl-devel \
            swig libpng-devel libjpeg-turbo-devel expat-devel \
        && dnf clean all \
        && pip3 install setuptools numpy \
        && wget https://download.osgeo.org/proj/proj-9.3.1.tar.gz \
        && tar zxvf proj-9.3.1.tar.gz \
        && cd proj-9.3.1/ \
        && mkdir build  \
        && cd build  \
        && cmake .. \
        && cmake --build . --parallel $(nproc)  \
        && cmake --install . --prefix /usr  \
        && cd ~  \
        && wget https://github.com/OSGeo/gdal/releases/download/v3.8.3/gdal-3.8.3.tar.gz  \
        && tar xvzf gdal-3.8.3.tar.gz  \
        && cd gdal-3.8.3/  \
        && mkdir build  \
        && cd build  \
        && cmake -DGDAL_BUILD_OPTIONAL_DRIVERS=OFF -DOGR_BUILD_OPTIONAL_DRIVERS=OFF .. \
        && cmake --build . --parallel $(nproc)  \
        && cmake --install . --prefix /usr ; \
        fi

RUN git clone https://github.com/CIROH-UA/ngen-datastream.git
WORKDIR ${FUNCTION_DIR}
RUN pip3 install -e "${FUNCTION_DIR}/forcingprocessor"

RUN groupadd -r mygroup && useradd -r -g mygroup myuser
RUN chown -R myuser:mygroup ${FUNCTION_DIR}


