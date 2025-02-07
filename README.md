# TrustSource Scanner

The **ts-scan** scanner is a powerful command-line tool designed for scanning package dependencies, generating Software Bill of Materials (SBOM) files, and analyzing existing SBOMs for security and compliance insights. It supports multiple SBOM formats, including SPDX and CycloneDX, allowing users to integrate it seamlessly into their software supply chain workflows.


## Description

The **ts-scan** scans a project for dependencies and stores the results using either its internal format or one of the supported SBOM formats: SPDX or CycloneDX. It currently supports **PyPI**, **Maven**, **NuGet**, and **NPM** but can also utilize [Syft](https://github.com/anchore/syft) as a backend allowing it to scan Docker containers.

Once dependencies are collected, the **ts-scan** can be used to either upload results to the [TrustSource](https://www.trustsource.io) application, perform security analysis of components by identifying known vulnerabilities, or conduct an in-depth analysis of each package. The goal of the in-depth analysis is to extract license and copyright information, detect cryptographic algorithms, identify code snippets, or detect malware by applying its own analyzers or integrating with external tools such as [scancode-toolkit](https://github.com/aboutcode-org/scancode-toolkit), [SCANOSS](https://www.scanoss.com), and [YARA](https://virustotal.github.io/yara/).

The **ts-scan** can be seamlessly integrated into CI/CD pipelines, enabling automated security and compliance checks continuously. It can be configured to break a build if vulnerabilities or legal issues are detected, ensuring compliance early in the development process. Additionally, it can be used alongside SCM hooks on developers' machines for pre-commit checks or execute long-running in-depth analyses remotely during release builds.

## Installation

**ts-scan** is available as a *PyPI* package. To install, you will require a recent *Python (>= 3.10)* version installed and *pip (>=22.0)*. Generally *pip* is already contained in your *Python* distribution but if not, follow pip's [installation instruction](https://pip.pypa.io/en/stable/installing/).

### Installation from the PyPI repository

```shell
pip install ts-scan
```

### Installation from a local folder

```shell
git clone https://github.com/trustsource/ts-scan.git
cd <path to the ts-scan repo, typically ts-scan>
pip install ./ --process-dependency-links
```

### Installation as a Docker image

For some scenarios you may want to provide **ts-scan** inside a Docker container, e.g. to prevent issues from version conflicts. 

> [!CAUTION]
>
> PLEASE NOTE: Scanning of Docker images using Syft from within the *ts-scan* Docker image is **not** supported for security reasons. 



#### Build a Docker image containing ts-scan (x86-64)

```shell
cd <path to the ts-scan>
docker build -t ts-scan .
```

#### Build a Docker image containing ts-scan (ARM)

```shell
cd <path to the ts-scan>
docker buildx build --platform linux/amd64 -t ts-scan .
```

Reason for this is, that pyminr - the encryption scanner - might fail to install on ARM chips.

#### Use ts-scan from the Docker image

```shell
docker run ts-scan <COMMAND>
```


## Usage

The **ts-scan** functionality is divided into a set of commands based on the intended goal. The following commands are available:

| Command	| Description 	|
|----------	| -----------	|
| [scan](#scan) 		| Scan for package dependencies |
| [analyse](#analyse) 	| Perform an in-depth analysis of a scan or an SBOM file |
| [check](#check)		| Check packages for legal issues and vulnerabilities |
| [upload](#upload)		| Upload scan and analysis results to the TrustSource application |
| [import](#import)		| Import SPDX and CycloneDX files directly into the TrustSource application |

To display a list of all available commands, use:

```shell
ts-scan --help
```

To get details about a specific command, use:

```shell
ts-scan <COMMAND> --help
```


## Scan

The **scan** command searches for package dependencies in your project. By providing a path, ts-scan automatically detects supported package management systems and extracts a full dependency tree. The scan results can be stored in a file using either the internal TS format or one of the supported SBOM formats: SPDX or CycloneDX.

To execute a scan and store results into a file, use:

```shell
ts-scan scan -o <path to the output file> [-f <format>] <path to the project directory>
```

The ```-f <format>``` option controls the output format and can be:

* ```ts``` - the TrustSource internal format (default)
* ```spdx-[tag|json|yaml|xml]``` - One of the SPDX formtas, e.g. ```spdx-json```
* ```cyclonedx-[json|xml]``` - One of the CycloneDX formats, e.g. ```cyclonedx-json```

### Options

**ts-scan** contains some general options as well as options that only apply while scanning specific package types. The package specific options are prefixed by the type of the package management system. We use the [Package URL Type](https://github.com/package-url/purl-spec/blob/master/PURL-TYPES.rst) as a prefix. The following options are valid for most supported package management system:

* ```--[maven|npm|nuget|pypi]:ignore``` - Disable scanning dependencies of the type   
* ```--[maven|npm|nuget]:executable``` - Specify a path to the PM executable
* ```--[maven|npm|nuget]:forward``` - Forward arguments to the PM's executable

The full list of options including PM specific options can be printed using:

```shell
ts-scan scan --help
```
 
#### Scanner executable path

While scanning for  Maven, Node and NuGet dependencies, ***ts-scan*** calls corresponding package manager executables. For example, in order to specify a path to the Maven excutable use the following option

```shell
ts-scan scan --maven:executable /opt/local/bin/mvn <PATH>
```

#### Forward custom parameters to a scanner executable

There are also options to forward parameters to a package manager executable. For example, in order to pass a settings file to Maven, one can use the following combination:

```shell
ts-scan scan --maven:foward --settings,customSettings.xml <PATH>
```

### Other options

* ```--verbose``` - Enables verbose mode (including output from PM executables, useful for debugging)
* ```--tag``` - Stores the current SCM tag in the scan  
* ```--branch``` - Stores the current SCM branch in the scan  


### Scan with Syft as a backend

**ts-scan** can use [Syft](https://github.com/anchore/syft) scanner as a backend for dependencies scanning. To enable the Syft scanner, use the following option:

```shell
ts-scan scan --use-syft <SOURCE>
```

As a source you can specify any type of sources accepted by Syft, for example a local filesystem path. For more details on supported formats please refer to [Syft Supported Sources](https://github.com/anchore/syft/wiki/supported-sources).

Before calling Syft, **ts-scan** tries to find the Syft executable in default locations, in order to specify a custom location use the following option:

```shell
ts-scan scan --use-syft --syft-path <syft executable> <SOURCE>
```

To pass custom parameters directly to Syft:

```shell
ts-scan scan --use-syft --Xsyft <option>,<value> <SOURCE>
```

#### Scan Docker images with Syft

Syft supports many different input types, and one of them is Docker images. To scan a local docker image, use the following command:

```shell
./ts-scan scan --use-syft -o <OUTPUT> docker:<DOCKER IMAGE>
```

## Analyse

The in-depth dependency analysis is performed using the **analyse** command, which takes a scan file as input in one of the supported formats: the internal TS format, SPDX, or CycloneDX. Depending on the dependency package, the tool locates its files and scans each one using [ts-deepscan](https://github.com/TrustSource/ts-deepscan). Additionally, it uses [SCANOSS](https://www.scanoss.com) to improve and enrich the collected in-depth scanning results. 

## Check


## Upload

```shell
ts-scan upload --project-name <TrustSource project name> --api-key <TrustSource API key> <path to the scan JSON file>
```

#### More info

```shell
ts-scan upload --help
```

### Import SBOMs

Supported formats

- SPDX RDF (spdx-rdf)
- SPDX JSON (spdx-json)
- CycloneDX (cyclonedx)

```shell
ts-scan import -f <SBOM format> -v <SBOM format version> --module <SBOM module name> --module-id <SBOM module id> --project-name <TrustSource project name> --api-key <TrustSource API key> <path to the SBOM file>
```

#### More info

```shell
ts-scan import --help
```

## License

[Apache-2.0](https://github.com/trustsource/ts-pip-plugin/blob/master/LICENSE)
