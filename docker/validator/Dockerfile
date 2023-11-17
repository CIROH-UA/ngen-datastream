# Define custom function directory
ARG FUNCTION_DIR="/ngen-cal"

FROM python:3.9 as build-image

RUN git clone -b run_folder_validation https://github.com/JordanLaserGit/ngen-cal.git
# RUN git clone https://github.com/NOAA-OWP/ngen-cal.git
# COPY ngen-cal/ /ngen-cal

RUN pip3 install --upgrade pip
RUN pip3 install -e "/ngen-cal/python/ngen_conf"
RUN pip3 install --no-cache-dir -r "/ngen-cal/requirements.txt"