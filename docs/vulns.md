# Scanning for vulnerabilities

**ts-scan** does also assess for known vulnerabilities against the **TrustSource vulnerability lake** using the `check` command. 


## Usage

Scan a directory for dependencies first and store results into the ```scan.json``` file.

```shell
ts-scan scan -o scan.json <DIRECTORY>
```

Next, check for known vulnerabilities: 

```shell
ts-scan check --vulns-only -o result.json --api-key <TrustSource API key> scan.json
```
**NOTE**: a TrustSource API key is required, it can be created in the TrustSource application.

The option ```--vulns-confidence <level>``` can be used to control the confidence level (```high```, ```medium```, ```low```) for matching components with affected products listed in security bulletins, such as product/vendor tuples in CVEs. The default value is ```high```, minimizing false positives as much as possible. Sometimes it can be useful to apply lower confidence level, for example use the following command to search with a ```medium```confidence level:  

```shell
ts-scan check --vulns-only --vulns-confidence medium -o result.json --api-key <TrustSource API key> scan.json
```


