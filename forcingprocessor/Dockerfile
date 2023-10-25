# Define custom function directory
ARG FUNCTION_DIR="/ngen-datastream/forcingprocessor"

FROM python:3.9 as build-image

# Include global arg in this stage of the build
ARG FUNCTION_DIR

# Get code
RUN git clone --depth 1 -b forcingprocessor https://github.com/CIROH-UA/ngen-datastream.git

# Use a slim version of the base Python image to reduce the final image size
FROM python:3.9-slim

# Include global arg in this stage of the build
ARG FUNCTION_DIR

# Set working directory to function root directory
WORKDIR ${FUNCTION_DIR}

# Copy in the built dependencies
COPY --from=build-image ${FUNCTION_DIR} ${FUNCTION_DIR}

RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r "${FUNCTION_DIR}/requirements.txt"

CMD ["python","nwmforcing2ngen.py","conf.json"]
