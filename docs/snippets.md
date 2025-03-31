# Scanning for software snippets

**ts-scan** also supports scanning for known algorithm snippets. Therefor **ts-scan** can apply **ts-deepscan** which implements the capabilitiy to create the winnowing fingerprints **SCANOSS** is creating in its worknech. This allows **ts-scan** to request the open source knowledge base from SCANOSS for identifcation of the files. 

Given you have scanned a maven project, a part of the result may look like this, describing the httpcore component :

```json
...
{
            "key": "mvn:org.apache.httpcomponents:httpcore",
            "name": "httpcore",
            "type": "maven",
            "namespace": "org.apache.httpcomponents",
            "repoUrl": "",
            "homepageUrl": "",
            "description": "",
            "checksum": "95167d269607b358ba3ed7030ccd336dad8591a0",
            "private": false,
            "versions": [
              "4.4.11"
            ],
            "dependencies": [],
            "licenses": [],
            "meta": {
              "sources": {
                "url": "https://repo.maven.apache.org/maven2/org/apache/httpcomponents/httpcore/4.4.11/httpcore-4.4.11-sources.jar",
                "checksum": {
                  "sha1": "95167d269607b358ba3ed7030ccd336dad8591a0"
                }
              },
              "purl": "pkg:maven/org.apache.httpcomponents/httpcore@4.4.11"
            },
            "package_files": [
              "/Users/YOU/.m2/repository/org/apache/httpcomponents/httpcore/4.4.11/httpcore-4.4.11-sources.jar"
            ],
            "license_file": null,
            "crypto_algorithms": []
          },
...
deepscans : {}
```

You may now assess the files of this component for known information. At the end of the file you will find a key **deepscans** with an empty document. 

```shell
ts-scan analyse -o myclient-analysed-SBOM.ts myclient-SBOM.ts
```

After executing the former command you will find the new document being extended in this section with detailed data per file, like in the following example.

```json
...
	"deepscans": {
    ...
    "mvn:org.apache.httpcomponents:httpcore": {
        "result": {
          "httpcore-4.4.11-sources/org/apache/http/HttpEntityEnclosingRequest.java": {
            "scanoss": {
              "wfp": "file=66b83406362326af33f0a7ee03e21f44,2017,httpcore-4.4.11-sources/org/apache/http/HttpEntityEnclosingRequest.java\n4=580f6570\n5=a61a9320\n6=89ee373b\n7=b0886638\n8=bd668b71,fb0d20c4\n9=028ead5a,cab55853,d7aead00\n11=93951dcd\n13=ff5dfccd\n14=064b3e26\n15=d3f942b8,8fe9d4f5,2a9536b0\n16=abbf89cb\n17=579ca428\n21=ec9057cf\n22=4273907d,64cdb0c4\n24=f76c9f40\n27=1ac38724,b2402c98\n30=e3b95bd8\n34=003e0fd8,3047c233,47acf246\n38=82fba22d\n39=25b13733,f0943a74\n40=16169a0f,c9e631f5,7f4c67b2\n41=30cbe494,d8c9a300\n44=8106c1da\n47=a22e5c36\n49=447042f1\n54=f77bcb6f\n58=2dccdd63\n"
            },
            "links": [
              {
                "purl": [
                  "pkg:github/apache/httpcore"
                ],
                "version": "4.3-beta1-rc1",
                "licenses": [
                  "Apache-2.0"
                ]
              }
            ]
          },
          "httpcore-4.4.11-sources/org/apache/http/impl/DefaultHttpServerConnection.java": {
            "scanoss": {
              "wfp": "file=9c8bfb26668a771b462072d38a60a0f6,2518,httpcore-4.4.11-sources/org/apache/http/impl/DefaultHttpServerConnection.java\n4=580f6570\n5=a61a9320\n6=89ee373b\n7=b0886638\n8=bd668b71,fb0d20c4\n9=028ead5a,cab55853,d7aead00\n11=93951dcd\n13=ff5dfccd\n14=064b3e26\n15=d3f942b8,8fe9d4f5,2a9536b0\n16=abbf89cb\n17=579ca428\n21=ec9057cf\n22=4273907d,64cdb0c4\n24=f76c9f40\n28=1ac38724,b2402c98\n30=235b7c46\n33=246462f0,a4a2fdf2\n35=351c8a91\n38=3edd0d02,0abd99fc\n40=e4bf6bcb,ef5d1f08\n45=bb5b769e,6bfc96ba\n52=cee709c8,85fbe786\n53=1be0cc05\n56=e290634a,19963438,163b4499,eebb31a2,de6d4c8d,bf7b4b60\n57=febf1c0e\n58=d5a9be8f\n59=3959e5c9,59ab756d\n60=92f8ce0e\n61=bb0a06bb\n63=405a0dd0\n"
            },
            "links": [
              {
                "purl": [
                  "pkg:github/apache/httpcomponents-core",
                  "pkg:maven/io.github.sunny-chung/httpcore5-parent"
                ],
                "version": "4.4.5-rc1",
                "licenses": [
                  "Apache-2.0"
                ]
              }
            ]
          },
  }, 
  ...
```

The **deepscans** section now contains detailed data as well as the fingerprints. Beware, complex components tend to run into several thousands lines of JSON documents when assessing on flie level. 

However, besides data on all the file data contained within a package, you will also find a **summary** section at the end of each component details section. This may look like:

```
...
"stats": {
	"total": 263,
	"finished": 263
}
"summary": {
	"licenses": [],
	"coyprights" : {},
	"crypto_algorithms": {},
	"incompatible_licenses": [],
	"links": {}
}
...
```

These sections are made for faster processing of findings. The **stats** section gives control over the processing status. Given, _finished_ is lower than _total_, some files were not successfully processed.

The **summary** section aggergates all details within the component. Often this contains more licenses than the declared licenses. the copyrights will add all data found within the particular component, So does the list of crypto algorithms. The list of *incompatible* licenses is the result from an analysis against the OSADL matrix. For example, if an Apache-2.0 and a GPL-2.0 would be identified, they would appear here as an incompatible pair.

The links-section contains the component references to packages that contain this fiel as well.   

> [!NOTE] 
>
> For this sort of integration we are using the public SCANOSS API, which has a limit of 1000 fingerprints per request. This may lead to longer execution times for larger modules, due to **ts-scan** breaking down the requests per component into several chunks. 
