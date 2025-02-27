# Scanning for encryption

**ts-scan** also supports to scan for encryption algorithms. Using the deepscan extension ***pyminr***, which ia a wrapper around the **minr** implementation by SCANOSS, DeepScan is able to assess files for known encryption implementations.

Encryption analysis is enabled by default. There are two options for the encryption analysis:

* *Analysis of a directory content.* Can be useful when only the source code from a directory has to be scanned

* *Analysis of the dependencies files.* In this case files of every dependency from a dependecy scan will be analysed as long as they are available. 

For example, after scanning a Maven project one can look for used encryption algorithms in the sources of every package as long as they are available in the Maven repository (For most OS packages hosten on Maven Central this will be the case).

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