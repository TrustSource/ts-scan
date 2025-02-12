# Use Case #01 - Auto Scan on Commit

One of the most relevant cases for **ts-scan** is to be executed upon new code is commited. 

## Why you would want to do this?

​	Benefits 

## Prerequisites

ddcd

## Steps to Success

Define the `.pre-commit.yml` file:

```
repos:
  - repo: local
    hooks:
      - id: ts-scan
        name: run ts-scan
        language: system
        entry: /bin/sh -c "ts-scan scan -o scan.json ./ && 
            ts-scan eval 
              --exit-with-failure-on-vulns 
              --base-url https://api.dev.trustsource.io 
              --api-key 3d3bb943-864b-4631-b0b0-2752a7ea2b4a 
              -o scan.vulns.json ./scan.json || 
              echo \"Evaluation results can be found in the scan.vulns.json\" && 
              exit 1
        pass_filenames: false
```

comments

## Further Considerations



## Related Topics

