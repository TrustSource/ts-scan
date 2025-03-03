![Supported Versions](https://img.shields.io/badge/Python-%203.10,%203.11,%203.12-blue) [![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/TrustSource/ts-scan/badge)](https://scorecard.dev/viewer/?uri=github.com/TrustSource/ts-scan) ![License](https://img.shields.io/badge/License-Apache--2.0-green)

# Overview

***ts-scan*** is the ultimate scanner resulting from several years of experience with scanning code for license information, vulnerabilities or malware across a plethora of sources, be it plain text files, packages, docker images or even binaries across as many environments as possible.

Thus, we strive to provide a sort of a suiss army knife for scanning in the most comprehensive and comfortable way. And since we were not educated to do all day long this sort of work, we designed it to support automation.

This help has been designed to support you in making the best use of it. To get a quick entry we outline different use cases and describe how to achieve the particular goal. A general article will give you an overview of the design and another article explains how to use ***ts-scan*** together with the ***TrustSource*** platform. However, ts-scan is standalone and can be used with every backend.

To get a quick intro, jump to any of the following use cases:

* [Architecture Overview & supported Ecosystems](/ts-scan/architecture)

* Capabilities

  - [Scanning for dependencies](/ts-scan/sbom) (creating SBOMs)
  - [Scanning for licenses](/ts-scan/licenses)
  - [Scanning for encryption](/ts-scan/encryption)
  - [Scan for Known Vulnerabilities](/ts-scan/vulns)
  - [Scan for malware](/ts-scan/malware)
  - [Scan for known software snippets](/ts-scan/snippets)

* Operations (WIP)

  - Scanning different artefacts
  - Storing and exporting scan results to different formats
  - Operating ts-scan inside a container


## General Thoughts

Each tool designer has a specific usage in mind, when he starts his work. This typically has to do with the way he has learned the job should be done. This also applies to ts-scan. We aimed to provide a tool that can be used inside an automated tool chain, and be maximally flexible to serve as many use cases as possible. 

This is why we have split the processing into different steps. To avoid misunderstanding, we describe the meaning behind the verbs a bot more in detail:   

1. **SCAN**
   Use this to determine an SBOM for a particular build artefact. It allows to assess a target - may be a folder, a docker image or a supported build file - for dependencies. The result will be a file written to disk. You may select between different output formats (ts, spdx, CycloneDX). See `ts-scan scan --help` for details on the CLI or [creating SBOMs](/ts-scan/sbom). 

2. **ANALYSE**
   This action allows to assess the identified dependencies in detail. It will take the scan and pull for each identified dependency the sources from either the package management system or your local repository and assess file by file for information. For performance reasons, we split this assessment from the prior step. 
   We support different types of analysis: 
   - Copyright
   - License identification, 
   - Crypto-algorithms 
   - SCANOSS fingerprints (and decoration) 
   - Yara rules  
   Except the malware-scanning - which has a different use case - they are all *enabled* by deafult. Thus, not passing additional parameters will execute them all. To reduce required time and unnecessary computing efforts, you may select  `--disable-deepscan` or `--disable-scanoss-api` options. 
   ANALYSIS delivers the result always in *TrustSource*-format, because not all of the findings have a home in the standard SPDX/CyDX formats. However, you may use CONVERT to transfer - not loss free - the results into one of the standards. 

3. **CHECK**
   Allows to evaluate the identified findings against the project specific policies. This has been in troduced to allow breaking builds or deployments depending on the findings. You may use CHECK to assess for: 
   - Vulnerabilities
   - Licenses & OSADL compatibility matrix
   - Weak encryption
   Today **ts-scan** takes the findings and transfers them to the **TrustSource** platform. There policies and assessments against these policies are organised and a result is returned. Read our [use case 03](/ts-scan/uc03-check) to learn how to drive your CI/CD using **ts-scan**.
   To achieve this, a *[TrustSource API-Key](https://trustsource.github.io/app-docs/keymgmt)* will be required. However, we plan to provide an option, to add a local policy file for local evaulation. 

4. **IMPORT**
   The IMPORT allows to transfer any 3rd party SBOM to the **TrustSource** platform. You may use this, to create new modules in  a project or update an existing module with this data. The IMPORT command will use the IMPORT function of the **TrustSource ** API. Thus, the conversion of the file will take place on the platform. 

5. **UPLOAD**
   This verb will become relevant, if you want to upload you scan or analysis results to the **TrustSource** platform. It allows to take any TrustSource result and push it in to the Platform for further management.

6. **CONVERT**
   Allows to convert SBOM elements from one format to another. You may see the [CONVERT](/ts-scan/convert)-section for more specifics on the different file formats and the obstacles for sound conversions. 

In our daily work this split has turned out to be very useful. We hope it is not too confusing. So feel free to leave us a note how you like it.

## Installing

See the [setup](/ts-scan/setup) section

## Getting Support

***ts-scan*** is open source and supported through this repository. As a TrustSource subscriber, you may contact [TrustSource support](mailto:support@trustsource.io) for help. As a community user, please [file a ticket with the repo](https://github.com/trustsource/ts-scan/issues).  

You may also find additional information and learning materials on specific scanning issues/topics in our open [TrustSource Knowledgebase](https://support.trustsource.io).

## Reporting Vulnerabilities

TrustSource supports a coordinated vulnerability disclosure procedure for its platform. ***ts-scan*** follows that schema and vulnerabilities identified should follow this procedure. Please find all details in our [Security](../security.md) Policy.



