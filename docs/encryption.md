# Scanning for encryption

**ts-scan** also supports to scan for encryption algorithms. Using the deepscan extension ***pyminr***, which ia a wrapper around the **minr** implementation by SCANOSS, DeepScan is able to assess files for known encryption implementations.

Encryption analysis is enabled by default. There are two options for the encryption analysis:

* *Analysis of a directory content.* Can be useful when only the source code from a directory has to be scanned

* *Analysis of the dependencies files.* In this case files of every dependency from a dependecy scan will be analysed as long as they are available. 

For example, after scanning a Maven project one can look for used encryption algorithms in the sources of every package as long as they are available in the Maven repository (For most OS packages hosten on Maven Central this will be the case).

> [! CAUTION]
>
> SCANOSS has extended its decoration capabilities with newer algorithms end of Feb 2025. As far as of today, we did not see the minr solution having received this capability as well. It is not fully clear, which part of the data will be bound to the commercial subscription or whether the data will be available in the public decoration capability soon as well. 
>
> However, using the TrustSource-SCANOSS integration, you may make use of all SCANOSS data within TrustSource. 

## Analysis of a directory content

```shell
ts-scan analyse -o scan.json <DIRECTORY>
```


## Analysis of the dependencies files

Scan a directory for dependencies first and store results into the ```scan.json``` file.

```shell
ts-scan scan -o scan.json <DIRECTORY>
```

Next, analyse every depedency from the scan and store the scan together with analysis results into the ```scan.analysed.json``` 

```shell
ts-scan analyse -o scan.analysed.json scan.json
```

## Analysis results

The analysis results can be found in the output file. The output file contains the original dependency scan as well as a ```deepscans``` section containing results for each dependency.  The following example shows a snippet from the scanning results of a Maven projects containing the ```mvn:org.apache.httpcomponents:httpclient``` dependency:

```json
{
  ...
  "deepscans": [
    ...
      "mvn:org.apache.httpcomponents:httpclient": {
        "results": {
          ...
          "httpclient-4.5.14-sources/org/apache/http/impl/auth/DigestScheme.java": {
            "crypto": [
              {
                "algorithm": "MD5",
                "coding": 128
              }
              ...
            ]
          },
          ...
        }
    ...
  ]
}

```

If some usage of an encryption algorithm is found in a source file, it appears in the results dictionary of that file under ```crypto``` category. In this case a possible usage of an ```MD5``` algorithm was found in the ```org/apache/http/impl/auth/DigestScheme.java``` in the ```org.apache.httpcomponents:httpclient``` package.  

*NOTE*: if several analysers found results all results appear in that dictionary but every analyser has its own category.

