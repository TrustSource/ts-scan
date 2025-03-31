# Convert

**ts-scan** allows to export its findings into typical standards such as *CycloneDX*, *SPDX* or the *TrustSource* format. This capability can be used to convert CyDX into SPDX or vice versa. 

Unfortunately, not all of the formats have the same power in all details. This mainly is a result from their history. SPDX for example, coming primarily from the license compliance, has much more powerful featurs when it comes to license clearing than CyDX. Thus, ***a conversion form SPDX to CyDX will not be loss free***. 

On the other hand, CyDX is much more capable to transport vulnerability or file specific information. Here the conversion into SPDX most likely will not be possible without information loss. However, we ensure, that a valid file stands at the end of the convesion. 

Currently the following specificatios are supported:

* Cyclone DX v1.6, v1.4
* SPDX v2.3, v2.2
* TrustSource v1.0

By default, exports will always provide the latest specification version. Currently you may not use CONVERT to write to an older version of the specification. However, you may import an older version and convert it into a valid newer version.

> [!NOTE]
>
> The conversion always will pass through the TrustSource format, which is our internal representation. Since TrustSource is not a standard, we can be more flexible. But it may be, that there are requirements we did not yet cover. So please, feel free to raise [issues](https://github.com/trustsource/ts-scan/issues), if you require additional features or are missing / loosing data.



## CyDX 2 SPDX

To convert a CycloneDX file with the name "MyCydx-file.json" in cyclonedx-json format into the SPDX file "MySPDX" in XML structure, use :

```shell
ts-scan convert -o MyNewSPDX.xml -of spdx-xml -f cyclonedx-json MyCydx-file.json
```

You may switch the output formats accordingly. ts-scan supports `[ts|spdx-tag|spdx-json|spdx-yaml|spdx-xml|cyclonedx-json|cyclonedx-xml]`

>  [!CAUTION]
>
> When transforming CycloneDX into SPDX, CBOM and data from other extensions will always be skipped! SPDX does not have an approoriate means to store this information in v2.3.  



## SPDX 2 CycloneDX 

To convert a SPDX file with the name "MySpdx-file.json" in spdx-json format into the CycloneDX file "MyNewCydx" in XML structure, use :

```shell
ts-scan convert -o MyNewCydx.xml --output-format cyclonedx-xml -f spdx-json MySpdx-file.json 
```

> [!CAUTION]
>
> When transforming SPDX into CycloneDX you must note that the structure will change drastically. The way relations are managed differs. This may lead to data loss.   



## SPDX 2 TrustSource

To convert a SPDX file with the name "MySpdx-file.json" in spdx-json format into the TrustSource file "MyNewTS-file" in JSON format, use :

```shell
ts-scan convert -o MyNewTS-file.json -of ts -f spdx-json MySpdx-file.json
```



## CycloneDX 2 TrustSource

To convert a CycloneDX file with the name "MyCydx-file.json" in cyclonedx-json format  into the TrustSource file "MyNewTS-file" in JSON format, use :

```shell
ts-scan convert -o MyNewTS-file.ts --output-format ts -f cyclonedx-json MyCydx-file.json 
```



## TrustSource 2 CycloneDX

By default **ts-scan** will always export into CycloneDX v1.6.. To convert a TrustSource file with the name "MySpdx-file.json" in spdx-json format into the CycloneDX file "MyNewCydx" in XML structure, use :

```shell
ts-scan convert -o MyNewCydx.xml -of cyclonedx-xml -f ts MyTrustSource-file.ts 
```

> [!CAUTION]
>
> DeepScan details will not be available in CycloneDX format. **ts-scan** will try to bundle information from all files related to a component into the component meatdata. But this does not leave room for the positions of the findings within a file or other sort of details avaialble to TrustSource files. 



## TrustSource 2 SPDX

By default, **ts-scan** will export into SPDX v2.3. To convert a SPDX file with the name "MySpdx-file.json" in spdx-json format into  into the SPDX file "MySPDX" in XML structure, use:

```shell
ts-scan convert -o MySPDX.xml --output-format spdx-xml -f cyclonedx-json MyCydx-file.json
```

> [!CAUTION]
>
> Deepscan details will not be available in SPDX files.  Especially DeepScan data, such as position of findings within files, quality of license matches, ect., can't be represented in SPDX.



