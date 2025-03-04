# Use Case #03 - Check for Known Vulnerabilities 

Noone wnats to work for the bin

## Why you would want to do this?

​	Benefits 

## Prerequisites

We suggest to use `pre-commit` to initiate the scan automatically. `pre-commit` is a Python based implementation that hooks in the git flow and allows to execute tests before a commit is completed. Only when the tests are successful, the commit is accepted. You may learn more about the tooling [here](https://pre-commit.com).

 

## Steps to Success

Scan a directory for dependencies first and store results into the ```scan.json``` file.



```
repos:
  - repo: local
    hooks:
      - id: ts-scan
        name: run ts-scan
        language: system
        entry: /bin/sh -c "ts-scan scan -o scan.json ./ && 
            ts-scan check 
              --exit-with-failure-on-vulns 
              --base-url https://api.dev.trustsource.io 
              --api-key YOUR_API_KEY
              -o scan.vulns.json ./scan.json || 
              echo \"Evaluation results can be found in the scan.vulns.json\" && 
              exit 1
        pass_filenames: false
```

This will execute ts-scan from the local installation and run a Check-action on the local code. The `exit-with-failure-on-vulns` option will cause **ts-scan** to check the findings for vulnearbilities and exit with an exit code of "1" in case there are findings. The results can be found in the `scan.vulns.json`.











```shell
ts-scan scan -o scan.json <DIRECTORY>
```

Next, check the scan using TrustSource application: 

```shell
ts-scan check -o result.json scan.json
```

## Further Considerations

We highly recommend not to add execessive file based analysis to your `pre-commit` scans. Scanning for encryption, malware or licenses may take more time than a developer might want to wait for a pre-commit check. 
