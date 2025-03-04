# Use Case #02 - SBOM 2 Git

Creating SBOMs meanwhile got sort of "***good development practise***". Thus, you should consider to use **ts-scan** at least to automatically provide an SBOM to your git repository whenever you create a new release. In the following you will learn the steps required to use a github action - could be replaced with any sort of CI/CD runner activity - to generate an SBOM whenever you initiate the creation of a new release and add the resulting SBOM automatically to the repository.

## Why you would want to do this?

* Good development practise
* Will increase the OpenSSF score for your repository
*  You are fine out when it comes to documentation, as everything is already done ;-)
*  Documentation remains alsways up to date



## Prerequisites

Given you host your repository at GitHub, there is not much to do. You may add the folder `.github` into your repository root and add there an addition folder `workflows`. In this folder you put the following YAML file:

```yaml


```

 

## Steps to Success

### 1.Do this

### 2.Do that

### 3.See the result





## Further Considerations

It might not be a good idea to add extensive scanning in this step....
