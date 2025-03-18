FROM python:3.12-slim
MAINTAINER Grigory Markin "gmn@eacg.de"

RUN mkdir -p /tmp/ts-scan
WORKDIR /tmp/ts-scan

COPY ./src ./src
COPY ./pyproject.toml ./LICENSE ./

RUN pip install ./

ENTRYPOINT ["ts-scan"]
CMD []