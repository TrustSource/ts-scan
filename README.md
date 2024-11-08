# TrustSource scanner

The **ts-scan** scans your project for all package depedencies. It supports following build systems

- Python (wheel)
- Maven
- Nuget
- NPM

The collected information is stored locally as JSON structure and can be posted to the TrustSource service for the analysis.  

## Installation

#### Requirements

- **pip** - is often already contained in the Python distribution but in some cases, please, follow the pip's [installation instruction](https://pip.pypa.io/en/stable/installing/) 

#### Installation from the PyPI repository

```shell
pip install ts-scan
```

#### Installation from a local folder

```shell
cd <path to the ts-pip-plugin>
pip install ./ --process-dependency-links
```

## Usage

### Help

```shell
ts-scan --help
```

### Scan

```shell
ts-scan scan -o <path to the output file> <path to the project directory>
```

#### Options

##### Ignore scanners

In order to ignore scanning of dependencies of a particular type, add a parameter

`--<name of the scanner type>:ignore`
For example, to ignore scanning of maven dependencies

```shell
ts-scan scan --maven:ignore <PATH>
```

##### Scanner executable path

While scanning for  Maven, Node and NuGet dependencies, ***ts-scan*** calls corresponding package manager executables. For example, in order to specify a path to the Maven excutable use the following option

```shell
ts-scan scan --maven:executable /opt/local/bin/mvn <PATH>
```

##### Forward custom parameters to a scanner executable

There are also options to forward parameters to a package manager executable. For example, in order to pass a settings file to Maven, one can use the following combination:

```shell
ts-scan scan --maven:foward --settings,customSettings.xml <PATH>
```

##### More info

```shell
ts-scan scan --help
```

### Scan with Syft

**ts-scan** can use [Syft](https://github.com/anchore/syft) scanner as a backend for dependencies scanning. To enable the Syft scanner, use the following option

```shell
ts-scan scan --use-syft <SOURCE>
```

A <SOURCE> can be any filesystem path or a "source" supported by Syft

Before calling Syft, **ts-scan** tries to find the Syft executable in default locations, in order to specify a custom location use the following option

```shell
ts-scan scan --use-syft --syft-path <syft executable> <SOURCE>
```

In order to pass custom parameters directly to Syft

```
ts-scan scan --use-syft --Xsyft <option>,<value> <SOURCE>
```

#### Scan Docker images with Syft

Syft supports many different input types, and one of them is Docker images. For more details on supported sources types, please, refer to the Syft's official documentation or use the Syft's help command. 

In order to scan a local docker image, use the following command

```shell
./ts-scan scan --use-syft -o <OUTPUT> docker:<DOCKER IMAGE>
```

### Upload

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
