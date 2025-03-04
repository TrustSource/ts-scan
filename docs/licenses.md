# Scan for licenses

**ts-scan** allows to assess packages for declared licenses and files (repository structures) for license indications (effective licenses). This section explains how to use **ts-scan** for this task and how to use the results, which can be written in *CycloneDX*, *SPDX* or *TrustSource* formats or directly uploaded to **TrustSource platform** for further processing.

License and copyright analysis are enabled by default. There are two options for the license and copyright analysis:

* *Analysis of a directory content.* Can be useful when only the source code from a directory has to be scanned

* *Analysis of the dependencies files.* In this case files of every dependency from a dependecy scan will be analysed as long as they are available. 

For example, after scanning a Maven project you can try to assess it for license and copyright information in the sources of every package as long as they are available in the Maven repository. For most OS packages hosted on Maven Central this will be the case. However, you may also configure **ts-scan** to use a private Repository instead (see below).

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

The analysis results can be found in the output file. The output file contains the original dependency scan as well as a ```deepscans``` section containing results for each dependency.  The following example shows a snippet from the scanning results of a Maven projects containing the ```mvn:com.github.java-json-tools:json-patch``` dependency:

```json
{
  ...
  "deepscans": [
    ...
      "mvn:com.github.java-json-tools:json-patch": {
        "results": {
          ...
          "json-patch-1.13-sources/com/github/fge/jsonpatch/JsonPatchException.java": {
            "comments": [
              {
                "licenses": [
                  "LGPL-3.0-only",
                  "Apache-2.0"
                ],
                "copyright": [
                  {
                    "clause": "Copyright (c) 2014, Francis Galiegue (fgaliegue@gmail.com)",
                    "holders": [
                      "Francis Galiegue"
                    ]
                  }
                ],
                "line": 1,
                "endLine": 18
              }
            ],
          ...
        }
      }
    ...
  ]
}

```

If some copyright or license information is found in comments in a source file, it appears in the results dictionary of that file under ```comments``` category. In this case, references to the licenses **LGPL-3.0-only** and **Apache-2.0** as well as the copyright notice were found in the ```json-patch-1.13-sources/com/github/fge/jsonpatch/JsonPatchException.java``` file inside the comment between lines 1 and 18 in the ```com.github.java-json-tools:json-patch``` package.  

> [!NOTE]
>
> If several analysers found results all results appear in that dictionary but every analyser has its own category.



