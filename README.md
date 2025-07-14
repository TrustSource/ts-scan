![Supported Versions](https://img.shields.io/badge/Python-%203.10,%203.11,%203.12-blue) [![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/TrustSource/ts-scan/badge)](https://scorecard.dev/viewer/?uri=github.com/TrustSource/ts-scan) ![License](https://img.shields.io/badge/License-Apache--2.0-green)

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

| Command	              | Description 	                                                             |
|-----------------------|---------------------------------------------------------------------------|
| [init](#init) 		      | Initialize a TrustSource project                  |
| [scan](#scan) 		      | Scan for package dependencies                                             |
| [analyse](#analyse) 	 | Perform an in-depth analysis of a scan or an SBOM file                    |
| [check](#check)		     | Check packages for legal issues and vulnerabilities                       |
| [upload](#upload)		   | Upload scan and analysis results to the TrustSource application           |
| [import](#import)		   | Import SPDX and CycloneDX files directly into the TrustSource application |
| [convert](#convert)   | Convert SBOM between supported formats (TS, SPDX, CycloneDX)              

To display a list of all available commands, use:

```shell
ts-scan --help
```

To get details about a specific command, use:

```shell
ts-scan <COMMAND> --help
```

## User Settings

By first time **ts-scan** is executed, a user settings file is created in the home directory at **$HOME/.ts-scan/config**. It contains an empty ```[default]``` profile. 
The user settings file can be used to store any option passed to the **ts-scan**. The groups of options can be grouped into profiles. 

An example of a user settings file is:

```toml
[default]
api_key="<TrustSource API key>"

[dev]
api_key="<TrustSource API key from the Dev account>"
project_name="TrustSource default Project in the Dev account"
```
The format is a dictionary with the option name in snake-case format as a key and a value. For example, if the **ts-scan** option for the project name is ```--project-name```, the corresponding key in the user settings file is ```project_name```.

When **ts-scan** is executed all options from the ```default``` profile are loaded as default values for the command line options. If an option is explicitly passed on the command line, it will override the default value. 

To select a profile, use the ```-p\--profile``` option. For example, to use the ```dev``` profile, use:

```shell
ts-scan -p dev upload MyScan.json
```

In this case the **ts-scan** will use the ```api_key``` and ```project_name``` from the ```dev``` profile for the upload.

## Init

The **init** command initializes a TrustSource project. It creates a configuration file in the provided directory, which can be used to store the project name and API key for future use. This is particularly useful for developers, where you may want to avoid passing the API key and project name as a command-line argument every time a new scan is going to be uploaded.

To initialize a project, use:

```shell
ts-scan init --project-name <TrustSource project name> --api-key <TrustSource API key> <path to the project directory>
```

Both parameters are optional, for example only a project name can be stored inside the project while the API key is stored in the [user settings file](#user-settings).

**Note**: the project settings override the user settings file and the explicitly passed command line options override the project settings. For example if the API key is passed on the command line, it will override the API key stored in the project settings file.

## Scan

The **scan** command searches for package dependencies in your project. By providing a path, ts-scan automatically detects supported package management systems and extracts a full dependency tree. The scan results can be stored in a file using either the internal TS format or one of the supported SBOM formats: SPDX or CycloneDX.

To execute a scan and store results into a file, use:

```shell
ts-scan scan -o <path to the output file> [-f <output format>] <path to the project directory>
```

The ```-f <output format>``` option controls the output format and can be:

* ```ts``` - the TrustSource internal format (default)
* ```spdx-[tag|json|yaml|xml]``` - One of the SPDX formtas, e.g. ```spdx-json```
* ```cyclonedx-[json|xml]``` - One of the CycloneDX formats, e.g. ```cyclonedx-json```

### Options

**ts-scan** contains some general options as well as options that only apply while scanning specific package types. The package specific options are prefixed by the type of the package management system. We use the [Package URL Type](https://github.com/package-url/purl-spec/blob/master/PURL-TYPES.rst) as a prefix. The following options are valid for most supported package management system:

* ```--[maven|gradle|npm|nuget|pypi]:ignore``` - Disable scanning dependencies of the type   
* ```--[maven|gradle|npm|nuget]:executable``` - Specify a path to the PM executable
* ```--[maven|gradle|npm|nuget]:forward``` - Forward arguments to the PM's executable

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
* ```--tag <TAG>``` - Stores the SCM tag ```<TAG>``` in the scan  
* ```--branch <BRANCH>``` - Stores the SCM branch ```<BRANCH>``` in the scan  


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
ts-scan scan --use-syft -o <OUTPUT> docker:<DOCKER IMAGE>
```

## Analyse

The in-depth dependency analysis is performed using the **analyse** command, which takes a scan file as input in one of the supported formats: the internal TS format, SPDX, or CycloneDX. Depending on the dependency package, the tool locates its files and scans each one using [ts-deepscan](https://github.com/TrustSource/ts-deepscan). Additionally, it uses [SCANOSS](https://www.scanoss.com) to improve and enrich the collected in-depth scanning results. The **analyse** command can also take a directory as input to directly scan files inside it.      

To analyse a scan or a directory and store results into a file, use:

```shell
ts-scan analyse [-f <input format>] [-o <output>] <path to the scan file or directory>
```

The ```-f <input format>``` option specifies the input format of the scan to be checked (if a scan file is provided as input) and accepts the same values as the ```<output format>``` of the [scan](#scan) command.

By default, the **analyse**, command applies [ts-deepscan](https://github.com/TrustSource/ts-deepscan) using its default configuration and extends the analysis results with data from SCANOSS API.

To disable or fine-tune specific analysis steps, you can use additional options.

### Options

* ```--disable-deepscan``` - Disables analysis using DeepScan.
* ```--disable-scanoss``` - Disables extending DeepScan results with SCANOSS data.
* ```--scanoss-api-key <SCANOSS API key>``` - A SCANOSS API key, required for accessing data provided by SCANOSS over non-public API. For more details, please refer to [SCANOSS](https://www.scanoss.com)   
* ```--Xdeepscan <OPTION>,<VALUE>``` - Forwards <OPTION> <VALUE> to the DeepScan **scan** command.

The ```--Xdeepscan```can be used to configure the DeepScan analysers. For example, to analyse a scan while setting a timeout (in seconds) per file, use:  

```shell
ts-scan analyse --Xdeepscan timeout,30 <path to the scan file or directory>
```

For more details on available options for DeepScan, please refer to [ts-deepscan documentation](https://github.com/TrustSource/ts-deepscan).

## Check

The **ts-scan check** command verifies project dependencies for legal issues and known vulnerabilities. It performs these checks using the TrustSource API and supports two modes:

1. A full check based on the corresponding TrustSource project settings (a TrustSource project is required; refer to [TrustSource](https://www.trustsource.io) for more details).

2. A single component check against the TrustSource vulnerability database.

By default, the **check** command performs a full check. To check only for vulnerabilities, use the ```--vulns-only``` option.

In addition to vulnerability checks, the full mode also detects potential legal issues, such as license incompatibilities between dependencies or conflicts with the planned distribution model.

Both modes support exiting with a non-zero error code (1) if vulnerabilities or legal issues are found, making it highly useful for integration into CI/CD workflows.


### Full scan check

To execute a full check, use the following command:

```shell
ts-scan check --project-name <TrustSource project name> --api-key <TrustSource API key> [-f <input format>] [-o <output>] <path to the scan file>
```

The options ```--project-name <TrustSource project name>```and ```--api-key <TrustSource API key>```are required for the full scan.

> [!NOTE]
>
> PLEASE NOTE: Before executing a full check, you need to create a project in the TrustSource application and [upload](#upload) the scan into the application. For more details, please refer to [TrustSource User Guide](https://www.trustsource.io) 

The ```-f <input format>``` option specifies the input format of the scan to be checked and accepts the same values as the ```<output format>``` of the [scan](#scan) command.

Optionally, using the ```-o <output>``` option, you can store the check results into a JSON file.

### Vulnerabilities-Only check

A vulnerabilities check can be performed by adding a ```--vulns-only``` option to the **check** command:

```shell
ts-scan check --vulns-only --api-key <TrustSource API key> [-f <input format>] [-o <output>] [--vulns-confidence low|medium|high] <path to the scan file>
```

A vulnerabilities-only check does not require creation of the project and uploading the scan before running the check.

The ```--vulns-confidence <level>``` option allows you to control the confidence level for matching components with affected products listed in security bulletins, such as product/vendor tuples in CVEs. The default value is ```high```, minimizing false positives as much as possible.


### Options

There are several useful options available for both modes, making it easier to integrate the **check** command into CI/CD pipelines:

* ```--exit-on-legal``` - Exit with a non-zero (1) exit code if legal violations are found (default: ```on```)
* ```--exit-on-vulns``` - Exit with a non-zero (1) exit code if vulnerabilities are found (default: ```on```)
* ```--Werror``` - Treat vulnerability/legal warnings as errors


## Upload

The **upload** command is used to upload scans to the [TrustSource App](https://www.trustsource.io) for the .... TBD:


```shell
ts-scan upload --project-name <TrustSource project name> --api-key <TrustSource API key> <path to the scan JSON file>
```

#### More info

```shell
ts-scan upload --help
```

## Import SBOMs

The **import** command is used to import SBOMs to the [TrustSource App](https://www.trustsource.io) for the .... TBD:

Supported import formats:

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

## Convert

To convert a SBOM between supported formats, use:

```shell
ts-scan convert [-f <input format>] [-of <output format>] [-o <output>] <path to the SBOM file>
```

The ```-f <input format>``` and the ```-of <output format>``` options specify the input format and the output format respectively and accept the same values as the <output format> of the scan command.

## License

[Apache-2.0](https://github.com/trustsource/ts-pip-plugin/blob/master/LICENSE)
