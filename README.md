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

More info

```shell
ts-scan scan --help
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
