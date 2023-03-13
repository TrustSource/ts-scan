# TrustSource PIP Plugin

The **ts-pip-plugin** scans a Python project for all installed pip modules. The plugin parses import statements of all project's source files and recursively extracts the complete module dependency tree. 
The collected information is posted to the TrustSource service or will store it locally as JSON structure.

## Installation

#### Requirements

- **pip** - is often already contained in the Python distribution but in some cases, please, follow the pip's [installation instruction](https://pip.pypa.io/en/stable/installing/) 

#### Installation from a local folder

```markdown
cd <path to the ts-pip-plugin>
pip install ./ --process-dependency-links
```

## Usage

```markdown
ts-pip-plugin <path to the project directory>
```

#### Requirements

- **ts-plugin.json** - settings file in the project's directory

## Project settings (ts-plugin.json)

- **project** : String - project name
- **credentials** : String [optional] - location of the file containing login information (userName and appKey) for the ECS service. Ignored: if a userName or appKey keys are present in the config file
- **userName** : String - TrustSource login name (optional)
- **appKey** : String - TrustSource key for apps
- **skipTransfer** : Bool - outputs the scan results into the stdout without submitting to the ECS service

## License

[ASL-2.0](https://github.com/trustsource/ts-pip-plugin/blob/master/LICENSE)
