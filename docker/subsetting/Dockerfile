ARG FUNCTION_DIR="/ngen-datastream"
FROM python:3.9 as build-image
ARG FUNCTION_DIR
RUN git clone https://github.com/CIROH-UA/ngen-datastream.git

FROM python:3.9-slim
ARG FUNCTION_DIR
WORKDIR ${FUNCTION_DIR}
COPY --from=build-image ${FUNCTION_DIR} ${FUNCTION_DIR}
RUN pip3 install --upgrade pip
RUN pip3 install -e "${FUNCTION_DIR}/subsetting"
