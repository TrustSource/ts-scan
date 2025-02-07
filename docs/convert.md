# Convert

**ts-scan** allows to export its findings into typical standards such as *CycloneDX*, *SPDX* or the *TrustSource* format. This capability can be used to convert CyDX into SPDX or vice versa. 

Unfortunately, not all of the formats have zthe same power in all details. This mainly is a result from their history. SPDX for example, coming primarily from the license compliance, has much more powerful featurs when it comes to license clearing than CyDX. Thus, a conversion form SPDX to CyDX will not be loss free. 

On the other hand, CyDX is much more capable to transport vulnerability or file specific information. Here the conversion into SPDX most likely will not be possible without information loss. However, we ensure, that a valid file stands at the end of the convesion. 

Currently the follwooing specificatios are supported:

* Cyclone DX v1.6, v1.4
* SPDX v2.3, v2.2
* TrustSource v1.0

The follwoing sections will address spüecific details to remind, when execution a conversion. 

## CyDX 2 SPDX



## SPDX 2 CyDX 



## SPDX 2 TrustSource



## CyDX 2 TrustSource



## TrustSource 2 CyDX



## TrustSource 2 SPDX





