# Use Case #03 - Check for Known Vulnerabilities 

Noone wnats to work for the bin

## Why you would want to do this?

​	Benefits 

## Prerequisites

We suggest to use `pre-commit` to initiate the scan automatically. `pre-commit` is a Python based implementation that hooks in the git flow and allows to execute tests before a commit is completed. Only when the tests are successful, the commit is accepted. You may learn more about the tooling [here](https://pre-commit.com).

 

## Steps to Success



## Further Considerations

We highly recommend not to add execessive file based analysis to your `pre-commit` scans. Scanning for encryption, malware or licenses may take more time than a developer might want to wait for a pre-commit check. 
