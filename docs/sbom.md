# Scan for dependencies (creating SBOMs)

The origin of our scanning efforts has been to create a Software Bill of Materials (SBOM). This is a different job, depending on the ecosystem. There are languages like C or C++, which are mainly organised through `include`directives in the files themselves, there are package manager driven languages like Python, Java or Java Script. 

Currently ts-scan has modules supporting a set of package manager driven systems as well as file based structures. The most recent list can bei found in the ts-scan repo or in the [Overview](/ts-scan/index).   
