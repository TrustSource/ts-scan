![Supported Versions](https://img.shields.io/badge/Python-%203.10,%203.11,%203.12-blue) [![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/TrustSource/ts-scan/badge)](https://scorecard.dev/viewer/?uri=github.com/TrustSource/ts-scan) [![OpenSSF Best Practices](https://www.bestpractices.dev/projects/10358/badge)](https://www.bestpractices.dev/projects/10358) ![License](https://img.shields.io/badge/License-Apache--2.0-green)

# Overview

***ts-scan*** is the ultimate scanner resulting from several years of experience with scanning code for license information, vulnerabilities or malware across a plethora of sources, be it plain text files, packages, docker images or even binaries across as many environments as possible.

Thus, we strive to provide a sort of a suiss army knife for scanning in the most comprehensive and comfortable way. And since we were not educated to do all day long this sort of work, we designed it to support automation.

This help has been designed to support you in making the best use of it. To get a quick entry we outline different use cases and describe how to achieve the particular goal. A general article will give you an overview of the design and another article explains how to use ***ts-scan*** together with the ***TrustSource*** platform. However, ts-scan is standalone and can be used with every backend.

To get a quick intro, jump to any of the following use cases:

- [Architecture Overview & supported Ecosystems](/ts-scan/architecture)
- [Installation](/ts-scan/setup) 
- Capabilities
	- See [Usage](/ts-scan/usage) page on general guidance
	- [Scanning for dependencies](/ts-scan/sbom) (creating SBOMs)
	- [Scanning for licenses](/ts-scan/licenses)
	- [Scanning for encryption](/ts-scan/encryption)
	- [Scan for Known Vulnerabilities](/ts-scan/vulns)
	- [Scan for malware](/ts-scan/malware)
	- [Scan for known software snippets](/ts-scan/snippets)
	
- Operations examples
  * [Scanning different artefacts](/ts-scan/multiscan)
  * [Auto-create SBOMs](/ts-scan/uc02-SBOOM2Git)
  * [Prevent check-in of vulnerable dependencies](/ts-scan/uc03-check)
  * [Converting between different SBOM formats](/ts-scan/convert)



## Getting Support

***ts-scan*** is open source and supported through this repository. As a TrustSource subscriber, you may contact [TrustSource support](mailto:support@trustsource.io) for help. As a community user, please [file a ticket with the repo](https://github.com/trustsource/ts-scan/issues).  

You may also find additional information and learning materials on specific scanning issues/topics in our open [TrustSource Knowledgebase](https://support.trustsource.io).

## Reporting Vulnerabilities

TrustSource supports a coordinated vulnerability disclosure procedure for its platform. ***ts-scan*** follows that schema and vulnerabilities identified should follow this procedure. Please find all details in our [Security](../security.md) Policy.

