# Installation

Installation is fairly simple. We do provide a ts-scan as PIP package. To install, you will require a recent (v3.10, v3.11 or v3.12 are tested) Python version installed and pip (v22+). Generally **pip**  is already contained in your Python distribution but if not, follow pip's [installation instruction](https://pip.pypa.io/en/stable/installing/).


### Installation from the PyPI repository

After pip is install you may install from the Pypi repo:

```
pip install ts-scan
```


### Installation from a local folder

Alternatively you may choose to clone the ts-scan repository and install the code directly in your environment: 

```
git clone https://github.com/trustsource/ts-scan.git
cd <path to the ts-scan repo, typically ts-scan>
pip install ./ --process-dependency-links
```


## Provide a Docker build

For some scenarios you may want to provide ts-scan inside a docker container, e.g. to prevent issues from version conflicts. 

> [!CAUTION]
>
> Scanning of Docker images using Syft from within the *ts-scan* Docker image is **not** supported for security reasons. 



### Build a Docker image containing ts-scan (AMD, intel, etc.)

```
cd <path to the ts-scan>
docker build -t ts-scan .
```


### Build a Docker image containing ts-scan (ARM)

```
cd <path to the ts-scan>
docker buildx build --platform linux/amd64 -t ts-scan .
```

Reason for this is, that pyminr - the encryption scanner - might fail to install on ARM chips.



### Use ts-scan from the Docker image

```
docker run ts-scan <COMMAND>
```

for further details see the use case from the [Overview](/ts-scan/index)



## Trouble Shooting

This section will contain hints on solving issues during the installation as soon as we get aware of issues. Feel free to report your questions and experiences in the [issues](https://github.com/trustsource/ts-scan/issues) section of this repo. 
