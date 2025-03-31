# Scanning multi builds 

**ts-scan** has been designed to handle multiple languages at once. This allows to scan mutli-builds, e.g. a Java backend and a Javascript frontend, with the same tool. The `scan` command will identify the environments used in the work directory and use the appropriate mechanism to identify the transitive dependencies for the SBOM. 

> [!NOTE]
>
> Make sure to start the scan in the corresponding path. If the work directory passed to **ts-scan** does not contain any remains of the build environment, **ts-scan** will just terminate with a `nothing to scan` message.

**ts-scan** supports the environments as outlined in the [architecture overview](/ts-scan/architecture). To learn about expansion plans, see the [roadmap](/ts-scan/roadmap). You may add languages by yourself. Feel free, we are happy to help!

However, **ts-scan** will always scan everything that it can find and combine the results into one result file. 

## Organising your scans

Depending on your organisation, it may be useful to either have all the findings in one list or in several. Staying with the example from above, assume we have a solution with a Java backend and Javascript based frontend.

### Combined results

Given you have only a small team of developers working on both, it may be useful to have all information in one place. In this case you would most likely provide the implementations in a single repository. Say you have the correpsonding `yarn.lock` and `pom.xml`in the `/src` folder, you would want to execute:

```shell
ts-scan scan -o scan-result.json .
```

**ts-scan** will identify the required environments and collect the transitive dependenices. First for maven, then for npm. It will determine the two dependency trees and append them together into _one_ result file.  The result file will contain *two* SBOMs added into *one* file. 

### Separate results

Given you have two different teams, you would most likely have the two solutions organised in two separate repositories. This  will prevent **ts-scan** from finding all in the same place. Thus, you will receive two scan results, most likely you want them to be uploaded into two different **modules** of your solution.

But if you have for some historical reason still both evironments in the same repository with the same root-folder **ts-scan ** would scan both. You may prevent this by skipping one of the languages and executing two scans:

```shell
ts-scan scan  -o scan-npm-result.json  -f cyclonedx.json --maven:ignore .
```

And to receive only the maven result, use:

```shell
ts-scan scan  -o scan-mvn-result.json  -f cyclonedx.json --npm:ignore .
```

The two scans then may be uploaded into different modules, e.g. _frontned_ and _backend_, within the same project. 
