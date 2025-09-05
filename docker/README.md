# Docker Configuration

This directory contains Docker configurations for building and running ngen-datastream components.

## Files

- `docker-compose.yml` - Multi-service orchestration for datastream components
- `Dockerfile.datastream-deps` - Base dependencies image (Amazon Linux 2023)
- `Dockerfile.datastream` - Main datastream application image
- `Dockerfile.forcingprocessor` - Forcing processor service image
- `config.json` - Docker daemon configuration with proxy settings

## Services

### datastream-deps
Base image with system dependencies and PROJ library for geospatial operations.

### datastream
Main application containing python_tools and configs directories.

### forcingprocessor
Specialized service for processing forcing data.

## Usage

```bash
# Build all services
docker compose -f docker/docker-compose.yml build

# Build specific service
docker compose -f docker/docker-compose.yml build datastream

# Set architecture (x86 or aarch64)
ARCH=aarch64 docker -f docker/docker-compose.yml compose build

# Build with custom tags
TAG=latest-x86 docker compose -f docker/docker-compose.yml build datastream-deps
TAG=latest-x86 docker compose -f docker/docker-compose.yml build datastream
TAG=latest-x86 docker compose -f docker/docker-compose.yml build forcingprocessor

# Push with custom tags
TAG=latest-x86 docker compose -f docker/docker-compose.yml push datastream-deps
TAG=latest-x86 docker compose -f docker/docker-compose.yml push datastream
TAG=latest-x86 docker compose -f docker/docker-compose.yml push forcingprocessor
```
