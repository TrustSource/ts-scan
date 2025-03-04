# Scan for dependencies (creating SBOMs)

The origin of our scanning efforts has been to create a Software Bill of Materials (SBOM). This is a different job, depending on the ecosystem. There are languages like C or C++, which are mainly organised through `include`directives in the files themselves, there are package manager driven languages like Python, Java or Java Script. 

Currently ts-scan has modules supporting a set of package manager driven systems as well as file based structures. The most recent list can bei found in the ts-scan repo or in the [Overview](/ts-scan/index).   

## How to scan

The **scan** command searches for package dependencies in your project. By providing a path, ts-scan automatically detects supported package management systems and extracts a full dependency tree. The scan results can be stored in a file using either the internal TS format or one of the supported SBOM formats: SPDX or CycloneDX.

To execute a scan and store results into a file, use:

```shell
ts-scan scan -o <path to the output file> [-f <output format>] <path to the project directory>
```

The ```-f <output format>``` option controls the output format and can be:

* ```ts``` - the TrustSource internal format (default)
* ```spdx-[tag|json|yaml|xml]``` - One of the SPDX formtas, e.g. ```spdx-json```
* ```cyclonedx-[json|xml]``` - One of the CycloneDX formats, e.g. ```cyclonedx-json```

## Options

**ts-scan** contains some general options as well as options that only apply while scanning specific package types. The package specific options are prefixed by the type of the package management system. We use the [Package URL Type](https://github.com/package-url/purl-spec/blob/master/PURL-TYPES.rst) as a prefix. The following options are valid for most supported package management system:

* ```--[maven|npm|nuget|pypi]:ignore``` - Disable scanning dependencies of the type   
* ```--[maven|npm|nuget]:executable``` - Specify a path to the PM executable
* ```--[maven|npm|nuget]:forward``` - Forward arguments to the PM's executable

The full list of options including PM specific options can be printed using:

```shell
ts-scan scan --help
```

### Scanner executable path

While scanning for  Maven, Node and NuGet, ... dependencies, ***ts-scan*** calls corresponding package manager executables. For example, in order to specify a path to the Maven excutable, use the following option:

```shell
ts-scan scan --maven:executable /opt/local/bin/mvn <PATH>
```

### Forward custom parameters to a scanner executable

There also is the option to forward parameters to a package manager executable. For example, in order to pass a settings file to Maven, one can use the following combination:

```shell
ts-scan scan --maven:foward --settings,customSettings.xml <PATH>
```

### Other options

* ```--verbose``` - Enables verbose mode (including output from PM executables, useful for debugging)
* ```--tag <TAG>``` - Stores the SCM tag ```<TAG>``` in the scan  
* ```--branch <BRANCH>``` - Stores the SCM branch ```<BRANCH>``` in the scan  



## Scan Docker files/images with Syft as a backend

**ts-scan** can use [Syft](https://github.com/anchore/syft) scanner as a backend for dependencies scanning. To enable the Syft scanner, use the following option:

```shell
ts-scan scan --use-syft <SCANTARGET>
```

As a scan target you can specify any type of sources accepted by Syft, for example a local filesystem path or docker images. For more details on supported formats please refer to [Syft Supported Sources](https://github.com/anchore/syft/wiki/supported-sources).

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

> [!NOTE] 
>
> Syft will be installed a part of ts-scan. You do not need to install it separately.





