# Use Case #02 - SBOM 2 Git

Creating SBOMs meanwhile got sort of "***good development practise***". Thus, you should consider to use **ts-scan** at least to automatically provide an SBOM to your git repository whenever you create a new release. In the following you will learn the steps required to use a github action - could be replaced with any sort of CI/CD runner activity - to generate an SBOM whenever you initiate the creation of a new release and add the resulting SBOM automatically to the repository.

## Why you would want to do this?

* Good development practise
* Will increase the OpenSSF score for your repository
* You are fine out when it comes to documentation, as everything is already done ;-)
* Documentation remains alsways up to date



## Prerequisites

There are many options to achieve the goal. One of them is to add the SBOM creation as part of a [pre-commit](https://pre-commit.com) action. This requires to have pre-commit installed.    

## Steps to Success

To achieve the automated SBOM geenration upon each commit, follow these steps: 

### 1. Create SBOM action script

Go to `.git/hooks`in your repository and add a `create-sbom.sh` with `touch create-sbom.sh` and add the following commands:

```sh
# Create a new SBOM file
ts-scan scan -o SBOM-cydx.json -f cyclonedx-json .
# Add the new file to the commit
git add SBOM-cydx.json
# Exit with a success status
exit 0
```

### 2. Make the scrip executable

Now allow to execute the script: `chmod +x create-sbom.sh` and change back to the root folder of your repository.

### 3. Add to pre-commit

Create the pre-commit action using `touch .pre-commit-config.yaml` with the following commands:

```yaml
  - repo: local
    hooks:
      - id: create-sbom
        name: Create SBOM file
        entry: .git/hooks/create-sbom.sh
        language: script
```

This will execute the script upon any push and ensure the SBOM provided in the repository stays always accurate. 

## Alternative 

An alternative would be to create the SBOM in a later step using a github action. Therefor add the folder `.github` into your repository root and add there the folder `workflows`. In this folder you put the following YAML file:

```yaml
repos:
  - repo: local
    hooks:
      - id: ts-scan
        name: run ts-scan
        language: system
        entry: /bin/sh -c "ts-scan scan -o SBOM.cydx -f cyclonedx-json ."

```

