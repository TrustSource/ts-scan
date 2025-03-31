# About ts format

***ts-scan*** delivers all scans using the TrustSource format as default. You may export the findings in a standard like CycloneDX or SPDX. But to leverage all potential of TrustSource, we recommend to use the TrustSource format. Since it is not a standard, we are more felxible to our needs. We do not need to run through a consortium to get our demands accepted, we just change it accrodngly. However, we keep compatibility to the standards. Exports will always be supported. Yes, data loss may occur.  



## Basic structure

In its current version 1.1 the format uses a tree structure to represent dependencies. All other formats are graph oriented representations. This is difficult to read for peopple, but simple to work with for machines. TrustSource decided to allow both. In the upcoming v1.2 we will keep to show the dependency structure as a tree, but allow to add grpah strutcured dependencies ain addition. This will help to better represent cyclic dependencies. 

As shown in the following snippet, the format consists mainly of four keys:

```json
[
  {
    "module": "",
    "moduleId": "", 
    "dependencies": [],
    "deepscans": {}
  }
]
```

While the first two are used for identification of the following entries, e.g. in the TrustSource Platform all scans belong either to a project or a module, the dependencies key holds the root node of the transitive dependencies section. The last key, is the deepscan root node.  In this section the deepscan of any element containing files will be found.

## Dependencies Section

Here is an example containing information for a package called **ts-java-client**. This has been the former communication client used to transfer scans to TrustSource.

```
[
  {
    "module": "ts-java-client",
    "moduleId": "mvn:de.eacg:ts-java-client:0.4.6", 
    "dependencies": [
    	{
    		"key": "mvn:de.eacg:ts-java-client",
    		"name": "ts-java-client",
    		"type": "maven",
    		"namespace": "de.eacg",
    		"repoUrl": "https://github.com/trustsource/ts-java-client",
    		"homepageUrl": "",
    		"description": "",
    		"checksum": "",
    		"private" : false,
    		"versions": [
    			"0.4.6"
    		],
    		"dependencies" : [],
    		"licenses": [
    			{
    				"name" : "MIT",
    				"url" : "https://raw.githubusercontent.com/trustsource/ecs-mvn-plugin/master/LICENSE",
            "kind" : "declared"
    			}
    		],
    		"meta" : {
					"sources" : {
						"url": "https://repo.maven.apache.org/maven2/de/eacg/ecs-java-client/0.4.6/ecs-java-client-0.4.6-sources.jar"},
					"purl" : "pkg:maven "
					},
					"package_files" : [],
          "license_file": null,
          "crypto_algorithms": []
    		},
    ],
   "deepscans": {}
   }
 ]
```

In the **dependencies** section you see the keys associated with each component indentified. most of them are self explanatory. In geenral this is the information declared in the apckage manager systems. **ts-scan** will populate these fields automatically. And again, you will find the **dependencies** key with another array. This will carry the transitive dependencies, each with another structure like the one you see for this component.  

When you execute the [ANALYZE](/ts-scan/usage#analyze) command, **ts-scan** will walk through the transtive depdencies tree and examine all file-locations, repectively collect the sources and assess them using the **ts-deepscan** implementation. To learn more about ts-deepscan see [here](https://trustsource.github.io/ts-deepscan).

## DeepScan Section 

The **deepscans** section will contain information gathered during the analysis phase. Therefor **ts-scan** uses **ts-deepscan** to conduct the analysis. **ts-deepscan** has sepcific analysers to assess files for license information, copyright remarks,crypto algorithms and - latest addon -  also malware via [yara](https://virustotal.github.io/yara/).

The following structure is a representation of deepscan results you may expect when running a standard analysis. **ts-scan** will automatically assess all files, it can get hold of for licenses, copyright remarks, create **SCANOSS fingerprints** and collect information from the SCANOSS database using the public interface.

> [!Note]
>
> Users of SCANOSS may provide their private API key to get a better response rate. See [scanning for knonw sources](/ts-scan/snippets) for more details. 

```json
...
"deepscans": {
      "mvn:de.eacg:ecs-java-client": {
        "result": {
          "ecs-java-client-0.4.6-sources/de/eacg/ecs/client/CheckResults.java": {
            "scanoss": {
              "wfp": "file=99b9f0eb2aa1f86d2e90e181abde56ca,5462,ecs-java-client-0.4.6-sources/de/eacg/ecs/client/CheckResults.java\n6=477286a0\n8=5e7c835d\n11=c7ac6489,24027ce8\n13=0076dc47\n14=d(...) 2\n225=2676ff36,0fe71b29\n230=f9a7bd23\n234=9660b8f3\n239=9c6be1e7\n"
            },
            "links": [
              {
                "purl": [
                  "pkg:maven/de.eacg/ecs-java-client",
                  "pkg:github/eacg-gmbh/ecs-java-client"
                ],
                "version": "0.4.6",
                "licenses": [
                  "LicenseRef-scancode-proprietary-license",
                  "MIT"
                ]
              }
            ]
          },
         ...
```

The first line contains the component. The results section lists the files it containes. Per file the scanoss section contains the fingerprint and links of the purls of the components where this fingerprint is known to appear. The licenses section contains the SPDX license identifiers of the licenses found.

 
