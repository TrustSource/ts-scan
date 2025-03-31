# Export findings

**ts-scan** allows to export its findings into local files as simple JSON or following standards such as *CycloneDX*, *SPDX* or *TrustSource* format.  One of the latter will be required to upload to the **TrustSource platform**.


To scan dependencies and store the results in ```spdx-json``` format in the file named ```scan.json```,  use:  

```shell
ts-scan scan -f spdx-json -o scan.json <PATH>
```

Supported output formats:

* *SPDX*: ```spdx-json```, ```spdx-xml```, ```spdx-yaml```, ```spdx-xml```
* *CycloneDX*: ```cyclonedx-json```, ```cyclonedx-xml```
* *TrustSource*: ts-json, default

You may use **ts-scan** to convert between different formats, see the [CONVERT](/ts-scan/convert) section for more details.
