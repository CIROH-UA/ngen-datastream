```
DATASTREAM_PATH="$(eval echo ~$USER)/ngen-datastream"
DATASTREAM_DOCKER="$DATASTREAM_PATH"/docker

cd $DATASTREAM_DOCKER
docker build -t datastream-deps:latest -f Dockerfile.datastream-deps . --no-cache --build-arg TAG_NAME=latest && \
docker build -t forcingprocessor:latest -f Dockerfile.forcingprocessor . --no-cache --build-arg TAG_NAME=latest && \
    docker build -t validator:latest -f Dockerfile.validator . --no-cache --build-arg TAG_NAME=latest
```