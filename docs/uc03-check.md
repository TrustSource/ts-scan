# Use Case #03 - Check for Known Vulnerabilities 

You may not want to allow your developers to add code containing known vulnerabilities. It is a managment decision whether you want this. In a first emotional reaction this may seem top be a brilliant idea. Thinking a bt deeper, it will not turn out to be such a good option. The same idea preventing the entry of new, vulnerable code will also prevent developers to provide workarounds or protections from known vulnerabilities in underlying components.

However, you must not necessarily block the push or pull request, you also might just want your developers to be informaed about the risks. 

## Why you would want to do this?

The earlier known vulnerabilities are identified, the lower the price to switch to other components.  

## Prerequisites

We suggest to use `pre-commit` to initiate the scan automatically. `pre-commit` is a Python based implementation that hooks in the git flow and allows to execute tests before a commit is completed. Only when the tests are successful, the commit is accepted. You may learn more about the tooling [here](https://pre-commit.com).

## Steps to Success

Scan a directory for dependencies first and store results into the ```scan.json``` file. Then execute the CHECK command to evaluate the SBOM against the project / module specific requirements and receive all known violations. This can be legal issues, vulnerabilities or crypto security. It is open to you, which restrictions you define.

```
repos:
  - repo: local
    hooks:
      - id: ts-scan
        name: run ts-scan
        language: system
        entry: /bin/sh -c "ts-scan scan -o scan.json ./ && 
            ts-scan check 
              --exit-with-failure-on-vulns 
              --base-url https://api.dev.trustsource.io 
              --api-key YOUR_API_KEY
              -o scan.vulns.json ./scan.json || 
              echo \"Evaluation results can be found in the scan.vulns.json\" && 
              exit 1
        pass_filenames: false
```

This will execute ts-scan from the local installation and run a Check-action on the local code. The `exit-with-failure-on-vulns` option will cause **ts-scan** to check the findings for vulnearbilities and exit with an exit code of "1" in case there are findings. The results can be found in the `scan.vulns.json`.

>  [!NOTE]
>
> Pleae note the ```YOUR API KEY``` variable. This will require a TrustSource API key. See the [online help](https://support.trustsource.io/hc/en-us/articles/8624792507922-How-to-manage-API-keys) to learn how to create one. We recommend not to store the API key in the config. You may use [github secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions) or a [local vault](https://github.com/mylofi/local-vault) to keep the key secret.  

The script above equals the following two commands. In the first step an SBOM is created.

```shell
ts-scan scan -o scan.json <DIRECTORY>
```

Then the CHECK command is used to verify tge SBOM and store the findings in the `scan.vulns.json` file. using TrustSource: 

```shell
ts-scan check -o scan.vulns.json scan.json
```

## Further Considerations

We highly recommend not to add execessive file based analysis to your `pre-commit` scans. Scanning for encryption, malware or licenses may take more time than a developer might want to wait for a pre-commit check. 

Please note: Given you are using TrustSource as a standalone version, you may need to modify ts-scan to use another than the public endpoint. 
