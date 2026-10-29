ARG DOCKER_CLI_IMAGE=docker:28-cli
FROM ${DOCKER_CLI_IMAGE} AS docker
FROM python:3.12-alpine
COPY --from=docker /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose
COPY --from=docker /usr/local/libexec/docker/cli-plugins/docker-buildx /usr/local/libexec/docker/cli-plugins/docker-buildx
ARG DOCKER_CLI_IMAGE=docker:28-cli
LABEL vmm.docker.cli.image=$DOCKER_CLI_IMAGE
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY app /app
COPY infra/runtime /runtime
CMD ["python", "server.py"]
