![Supported Versions](https://img.shields.io/badge/Python-%203.10,%203.11,%203.12-blue) [![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/TrustSource/ts-scan/badge)](https://scorecard.dev/viewer/?uri=github.com/TrustSource/ts-scan) [![OpenSSF Best Practices](https://www.bestpractices.dev/projects/10358/badge)](https://www.bestpractices.dev/projects/10358) ![License](https://img.shields.io/badge/License-Apache--2.0-green)

# Introduction

***ts-scan*** is the ultimate scanner resulting from several years of experience with scanning code for license information, vulnerabilities or malware across a plethora of sources, be it plain text files, packages, docker images or even binaries across as many environments as possible.

Thus, we strive to provide a sort of a suiss army knife for scanning in the most comprehensive and comfortable way. And since we were not educated to do all day long this sort of work, we designed it to support automation.

This help has been designed to support you in making the best use of it. To get a quick entry we outline different use cases and describe how to achieve the particular goal. A general article will give you an overview of the design and another article explains how to use ***ts-scan*** together with the ***TrustSource*** platform. However, ts-scan is standalone and can be used with every backend.

To get a quick intro, jump to any of the following use cases:

- [Architecture Overview & supported Ecosystems](/ts-scan/architecture)
- Capabilities
	* [Scanning for dependencies](/ts-scan/sbom) (creating SBOMs)
	* [Scanning for licenses](/ts-scan/licenses)
	* [Scanning for encryption](/ts-scan/encryption)
	* [Scan for Known Vulnerabilities](/ts-scan/vulns)
	* [Scan for malware](/ts-scan/malware)
	* [Scan for known software snippets](/ts-scan/snippets)
- Operations
	* [Scanning different artefacts](/ts-scan/multiscan)
	* [Storing and exporting scan results or converting between different formats](/ts-scan/convert)
	* [Automate SBOM generation](/ts-scan/uc02-SBOM2Git)
	* [Prevent vulnerable dependencies to be checked in](/ts-scan/uc03-check)

# Overview of Capabilities 

Typically each tool designer has a specific use case in mind, when starting his work. This also applies to **ts-scan**. We aimed to provide a tool, that can be used inside any automated CI/CD tool chain with a maximum of flexibility.  This is why we have split the processing into several steps, allowing to handle interim results. 

For abtter guidance, following will describe the meaning of the verbs:   

1. **SCAN**
  Use this to determine an SBOM for a particular build artefact. It allows to assess a target - may be a folder, a docker image or a supported build file - for dependencies. The result will be a file written to disk. You may select between different output formats (ts, spdx, CycloneDX). See `ts-scan scan --help` for details on the CLI or [creating SBOMs](/ts-scan/sbom). 

2. **ANALYSE**
	This action allows to assess the identified dependencies in detail. It will take the scan and pull for each identified dependency the sources from either the package management system or your local repository and assess file by file for information. Often this is bound into the first action. Bu we decided to separate this action for performance reasons. While it makes sense to verify the contents of a package when it enters the solution the first time, this activity must not be executed upon every commit. This will help you save time and resources.
	**ts-scan** uses [ts-deepscan](https://github.com/trustsource/ts-deepscan) to assess components. It will be installed automatically during the ts-scan setup. It supports the following types of analysis: 
	
	1. Copyright,
	2. License identification,
	3. Crypto-algorithms,
	4. SCANOSS fingerprints (and SBOM decoration)
	5. Yara rules
	
	By default all scans but yara are enabled. You may disable then using flags. See the corresponding scan section for details. 
	
3. **CHECK**
  Allows to evaluate the identified findings against the project specific policies. This has been introduced to allow breaking builds or deployments depending on the findings. You may use CHECK to assess for:

  1. Vulnerabilities
  2. Licenses & OSADL compatibility matrix
  3. Weak encryption
  Today **ts-scan** takes the findings and transfers them to the **TrustSource** platform. There policies and assessments against these policies are organised and a result is returned. Read our [use case #03](/ts-scan/uc03-check) to learn how to drive your CI/CD using **ts-scan**.
  To achieve this, a *[TrustSource API-Key](https://trustsource.github.io/app-docs/keymgmt)* will be required. However, we plan to provide an option, to add a local policy file for local evaulation.

4. **IMPORT**
  The IMPORT allows to transfer any 3rd party SBOM to the **TrustSource** platform. You may use this, to create new modules in  a project or update an existing module with this data. The IMPORT command will use the IMPORT function of the **TrustSource ** API. Thus, the conversion of the file will take place on the platform.**

5. **UPLOAD**
  This verb will become relevant, if you want to upload you scan or analysis results to the **TrustSource** platform. It allows to take any TrustSource result and push it in to the Platform for further management.

6. **CONVERT**
Allows to convert SBOM elements from one format to another. You may see the [CONVERT](/ts-scan/convert)-section for more specifics on the different file formats and the obstacles for sound conversions.

In our daily work this split has turned out to be very useful. We hope it is not too confusing. So feel free to leave us a note how you like it.

## 1. Executing a Scan 

You select your scan target and decide upon the desired outcome. Do you want to 

The **scan** command searches for package dependencies in your project. By providing a path, ts-scan automatically detects supported package management systems and extracts a full dependency tree. The scan results can be stored in a file using either the internal TS format or one of the supported SBOM formats: SPDX or CycloneDX.

To execute a scan and store results into a file, use:

```
ts-scan scan -o <path to the output file> [-f <output format>] <path to the project directory>
```

The `-f <output format>` option controls the output format and can be:

- `ts` - the TrustSource internal format (default)
- `spdx-[tag|json|yaml|xml]` - One of the SPDX formtas, e.g. `spdx-json`
- `cyclonedx-[json|xml]` - One of the CycloneDX formats, e.g. `cyclonedx-json`

### Options

**ts-scan** contains some general options as well as options that only apply while scanning specific package types. The package specific options are prefixed by the type of the package management system. We use the [Package URL Type](https://github.com/package-url/purl-spec/blob/master/PURL-TYPES.rst) as a prefix. The following options are valid for most supported package management system:

- `--[maven|npm|nuget|pypi]:ignore` - Disable scanning dependencies of the type
- `--[maven|npm|nuget]:executable` - Specify a path to the PM executable
- `--[maven|npm|nuget]:forward` - Forward arguments to the PM's executable

The full list of options including PM specific options can be printed using:

```
ts-scan scan --help
```

#### Scanner executable path

While scanning for Maven, Node and NuGet dependencies, ***ts-scan*** calls corresponding package manager executables. For example, in order to specify a path to the Maven excutable use the following option

```
ts-scan scan --maven:executable /opt/local/bin/mvn <PATH>
```

#### Forward custom parameters to a scanner executable

There are also options to forward parameters to a package manager executable. For example, in order to pass a settings file to Maven, one can use the following combination:

```
ts-scan scan --maven:foward --settings,customSettings.xml <PATH>
```

#### Configuring private Repositories as source

It is possible to pass arguments or complete configurations to the package manager. This may be useful in case you want it to use a private registry instead the public one, for example. The `--[maven|npm|nuget]:forward` - option allows to pass arguments to the package manager's executable.

### Other options

- `--verbose` - Enables verbose mode (including output from PM executables, useful for debugging)
- `--tag <TAG>` - Stores the SCM tag `<TAG>` in the scan
- `--branch <BRANCH>` - Stores the SCM branch `<BRANCH>` in the scan

### Scan with Syft as a backend

**ts-scan** can use [Syft](https://github.com/anchore/syft) scanner as a backend for dependencies scanning. We added this to enable a comprehensive docker image processing. It is not active by default, to enable the Syft scanner, use the following option:

```
ts-scan scan --use-syft <SOURCE>
```

As SOURCE you can specify any type of sources accepted by Syft, for example a local filesystem path or a docker image. For more details on supported formats please refer to [Syft Supported Sources](https://github.com/anchore/syft/wiki/supported-sources).

Before calling Syft, **ts-scan** tries to find the Syft executable in default locations, in order to specify a custom location use the following option:

```
ts-scan scan --use-syft --syft-path <syft executable> <SOURCE>
```

To pass custom parameters directly to Syft:

```
ts-scan scan --use-syft --Xsyft <option>,<value> <SOURCE>
```

#### Scan Docker images with Syft

Syft supports many different input types, and one of them is Docker images. To scan a local docker image, use the following command:

```
ts-scan scan --use-syft -o <OUTPUT> docker:<DOCKER IMAGE>
```

## 2. Analysing a Scan 

The in-depth dependency analysis is performed using the **analyse** command, which takes a scan file as input in one of the supported formats: the internal TS format, SPDX, or CycloneDX. Depending on the dependency package, the tool locates its files and scans each one using [ts-deepscan](https://github.com/TrustSource/ts-deepscan). Additionally, it uses [SCANOSS](https://www.scanoss.com/) to improve and enrich the collected in-depth scanning results. The **analyse** command can also take a directory as input to directly scan files inside it.

To analyse a scan or a directory and store results into a file, use:

```
ts-scan analyse [-f <input format>] [-o <output>] <path to the scan file or directory>
```

The `-f <input format>` option specifies the input format of the scan to be checked (if a scan file is provided as input) and accepts the same values as the `<output format>` of the [scan](https://github.com/TrustSource/ts-scan#scan) command.

By default, the **analyse**, command applies [ts-deepscan](https://github.com/TrustSource/ts-deepscan) using its default configuration and extends the analysis results with data from SCANOSS API.

To disable or fine-tune specific analysis steps, you can use additional options.

### Options

- `--disable-deepscan` - Disables analysis using DeepScan.
- `--disable-scanoss` - Disables extending DeepScan results with SCANOSS data.
- `--Xdeepscan <OPTION>,<VALUE>` - Forwards to the DeepScan **scan** command.

The `--Xdeepscan`can be used to configure the DeepScan analysers. For example, to analyse a scan while setting a timeout (in seconds) per file, use:

```
ts-scan analyse --Xdeepscan timeout,30 <path to the scan file or directory>
```

For more details on available options for DeepScan, please refer to [ts-deepscan documentation](https://github.com/TrustSource/ts-deepscan). 

> [!NOTE]
>
> To allow the processing of even large or very large SBOMs in reasonable time, **ts-deepscan** is developed to scale. However, the TrustSource platform is cloud hosted and provides a DeepScan-Scaleout that leverages the massive parallel processing capabilities of deepscan. You may define the hardware you want to use and it will automatically ramp up all hardware, initaite and perform the scans, transfer the findings to TrustSource or your own target and ramp down all infrastructure afterwards. This can happen in your own or our data center.  The ***DeepScan Scaleout*** has been designed to scan thousands of repositories at a snap.

## 3. Verify State against Policies

The **ts-scan check** command verifies project dependencies for legal issues and known vulnerabilities against project specific policies. It performs these checks using the TrustSource API - where the settings are stored. It supports two modes:

1. A full check based on the corresponding TrustSource project settings (a TrustSource project is required; refer to [TrustSource](https://www.trustsource.io/) for more details).
2. A single component check against the TrustSource vulnerability database.

By default, the **check** command performs a full check. To check only for vulnerabilities, use the `--vulns-only`option.

In addition to vulnerability checks, the full mode also detects potential legal issues, such as license incompatibilities between dependencies or conflicts with the planned distribution model.

Both modes support exiting with a non-zero error code (1) if vulnerabilities or legal issues are found, making it highly useful for integration into CI/CD workflows.

### Full scan check

To execute a full check, use the following command:

```
ts-scan check --project-name <TrustSource project name> --api-key <TrustSource API key> [-f <input format>] [-o <output>] <path to the scan file>
```

The options `--project-name <TrustSource project name>`and `--api-key <TrustSource API key>`are required for the full scan.

> [!NOTE]
>
> Before executing a full check, you need to create a project in the TrustSource application and [upload](https://github.com/TrustSource/ts-scan#upload) the scan into the application. To learn more on **TrustSource**, please refer to **[TrustSource App](https://app.trustsource.io/)**

The `-f <input format>` option specifies the input format of the scan to be checked and accepts the same values as the `<output format>` of the [scan](https://github.com/TrustSource/ts-scan#scan) command.

Optionally, using the `-o <output>` option, you can store the check results into a JSON file.

### Vulnerabilities-Only check

A vulnerabilities check can be performed by adding a `--vulns-only` option to the **check** command:

```
ts-scan check --vulns-only --api-key <TrustSource API key> [-f <input format>] [-o <output>] [--vulns-confidence low|medium|high] <path to the scan file>
```

A vulnerabilities-only check does not require creation of the project and uploading the scan before running the check.

The `--vulns-confidence <level>` option allows you to control the confidence level for matching components with affected products listed in security bulletins, such as product/vendor tuples in CVEs. The default value is `high`, minimizing false positives as much as possible.

### Further Options

There are several useful options available for both modes, making it easier to integrate the **check** command into CI/CD pipelines:

- `--exit-on-legal` - Exit with a non-zero (1) exit code if legal violations are found (default: `on`)
- `--exit-on-vulns` - Exit with a non-zero (1) exit code if vulnerabilities are found (default: `on`)
- `--Werror` - Treat vulnerability/legal warnings as errors

## 4. Import 3rd Party SBOMs to TrustSource

Sometimes you may want to import existing scans and assess these further. Whether your suppliers provided you with SBOMs, they stem from a purchased 3rd party product or you just created them with a another scanner does not matter. Every SBOM in SPDX v2.2 or v2.3 or any CycloneDX in v1.4 or v1.6 can be imported to TrustSource for further surveillance and treatment.

You may directly send the file to the TrustSource API, see the [API-docs](https://trustsource.github.io/api-docs) for more information or use **ts-scan**. Supported import formats:

- SPDX RDF (spdx-rdf)
- SPDX JSON (spdx-json)
- CycloneDX (cyclonedx)

To import a 3rd party SBOM, use

```
ts-scan import -f <SBOM format> -v <SBOM format version> --module <SBOM module name> --module-id <SBOM module id> --project-name <TrustSource project name> --api-key <TrustSource API key> <path to the SBOM file>
```

## 5. Upload data to TrustSource

Our understanding is that you do not want to produce SBOMs for the sake of SBOMs or because some legal directive requires you to do so. we want the SBOMs to become an integral part of your development efforts and software life-cycle management activities. It builds a relevant piece of information that - when automatically created throughout our software lifecycle - will contain relevant information for the management of the product.

With TrustSource, we have made the SBOM the essential piece of truth, which is guiding the Risk Management, the Vulnerability handling and reporting the complete Release Management. Therefor the SBOM should not only be pushed into a repostory. It should be activated and used as the binding element between the management and the development, ensuring a valid picture for every manager. To learn more, see the [TrustSource website](https://ww.trustsource.io).

The **upload** command is used to upload scans to the [TrustSource App](https://www.trustsource.io/) use:

```
ts-scan upload --project-name <TrustSource project name> --api-key <TrustSource API key> <path to the scan JSON file>
```

Get more options, e.g. dirceting to a specific enpoint etc. from the help: 

```
ts-scan upload --help
```



# Getting Support

***ts-scan*** is open source and supported through this repository. As a TrustSource subscriber, you may contact [TrustSource support](mailto:support@trustsource.io) for help. As a community user, please [file a ticket with the repo](https://github.com/trustsource/ts-scan/issues).  

You may also find additional information and learning materials on specific scanning issues/topics in our open [TrustSource Knowledgebase](https://support.trustsource.io).

# Reporting Vulnerabilities

TrustSource supports a coordinated vulnerability disclosure procedure for its platform. ***ts-scan*** follows that schema and vulnerabilities identified should follow this procedure. Please find all details in our [Security](../security.md) Policy.

