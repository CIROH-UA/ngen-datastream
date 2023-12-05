ARG FUNCTION_DIR="/ngen-datastream"
FROM python:3.9 as build-image

ARG FUNCTION_DIR
WORKDIR /tmp
RUN git clone https://github.com/CIROH-UA/ngen-datastream.git

FROM python:3.9-slim
ARG FUNCTION_DIR
WORKDIR ${FUNCTION_DIR}
COPY --from=build-image /tmp/ngen-datastream ${FUNCTION_DIR}
RUN pip3 install --upgrade pip && pip3 install -e "${FUNCTION_DIR}/forcingprocessor"

RUN groupadd -r mygroup && useradd -r -g mygroup myuser
RUN chown -R myuser:mygroup ${FUNCTION_DIR}
USER myuser

