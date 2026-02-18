# Operate ts-scan in a docker container

**ts-scan** can be operated in a container. This might be useful, if you want to operate it in a CI/CD chain or as part of a software factory setup and prevent issues with installation, different python versions, etc..

## Pull the docker image
We do maintain a docker image that includes all supported package management systems. This has the advantage, that you must not setup the package managers to asses particular packagemanagement systems. Whenever ts-scan finds the indication of a supported system, it will use it to determine the trasnsitive dependencies.  
Whenever we provide a new version of ts-scan, the docker image is automatically build and uploaded to dockerhub, using the ts-scan version as tag. Pulling the <code>latest</code> tag will always pull the updated version. You may make use of it in your code pipelines.

```shell
docker pull ts-scan:latest
```

## Build the docker image

To simplify usage within docker, we provided a dockerfile in the root of the repository. It will build on the official `python3.12-slim` image.  

> [!NOTE]
>
> Some libraries used by **ts-deepscan**, the file assessment tool, are implemented more natively. This leads to environment specific builds of the dockerfile. Please make sure to remember, when preparing for distributed use.


#### Build a docker image containing ts-scan (x86-64)

Clone the repo and 

```shell
cd <path to the ts-scan>
docker build -t ts-scan .
```

#### Build a docker image containing ts-scan (ARM)

Due to some restrictions ARM processors will require som, modified build. 

```shell
cd <path to the ts-scan>
docker buildx build --platform linux/amd64 -t ts-scan .
```

Reason for this difference is, that `pyminr` - the crypto scanner - might fail to install on ARM chips. 

Also Scancode is using some libs in the default installation, which are not available to the ARM platform. There we provide only the mini-variant. However, this is covered by **ts-scan** setup routine and does not require your attention. 

## Use ts-scan from the docker image

```shell
docker run ts-scan <COMMAND>
```

Replace `<COMMAND>` with whatever action you want to perform. See our [use cases](/ts-scan/uc01-autoSoCommit) for more details. 

>  [!CAUTION] 
>
> Scanning of Docker images using Syft from within the *ts-scan* Docker image is **not** supported for security reasons! It would require excessive privileges, so that we recommend to scan docker images from local.

