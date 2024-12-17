FROM python:3.12-slim
MAINTAINER Grigory Markin "gmn@eacg.de"

RUN mkdir -p /tmp/ts-scan
WORKDIR /tmp/ts-scan

COPY ./ts_scan ./ts_scan
COPY ./ts-scan ./_config.yml ./setup.py ./setup.cfg ./LICENSE ./MANIFEST.in ./

RUN pip install ./

ENTRYPOINT ["ts-scan"]
CMD []