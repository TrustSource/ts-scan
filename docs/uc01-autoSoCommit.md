# Use Case #01 - Auto Scan and Publish upon Commit

One of the most relevant cases for **ts-scan** is to be executed whenever new code is commited to a repository. We suggest to run a scan every time something is commited to the repository. 

## Why you would want to do this?

The earlier you identify odd code, the less expensive it will be to remove or fix the code. All the integration work, all the testing will not need to happen when your Developers would have knwon the impact *before* they added the particular library. TrustSource provide a [CHECK](/ts-scan/index) verb to test particular libraries, components or files from the CLI before adding them. We also recommend to either use the free [TrustSource Vulnerability Lake](https://vl.trustsource.io) or the platform specific UI to verify known data on components *before* you aill even add them in to the code.  

However, whether this will always be done when time is calling may be written on a different card. But the very first step you may start ensuring that your developers will take the verification requirement serious is, when you require them to pass a successful verification upon checking in their work results. We recommend using [pre-commit](https://pre-commit.com) to ensure such govervnance.

This will prevent your developers from commiting dependencies with known vulnerbailities (or weak crypto algorithms, or bad licenses, etc.)

## Prerequisites

The first step is to setup pre-commit, see [here](https://pre-commit.com/#install) for more details. Pre-commit will perform tests *before* the code is accepted as a commit to the repository. 

> [!NOTE]
>
> You also may decide to include this action into a Git-Workflow, e.g. when the build action is part of an automated CI/CD-chain waiting for the next commit. This also would work. The difference to our suggestion is that *pre-commit* prevents the unwanted extension to even enter the repository.  

Please clarify the intended behaviour within your developer community first. See below for further thoughts.

## Steps to Success

After having installed pre-commit, amend the `.pre-commit.yml` file as follows:

```yaml
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

> [!NOTE]  
>
> Pleae note the ```YOUR API KEY``` variable. This will require a TrustSource API key. See the [online help](https://support.trustsource.io/hc/en-us/articles/8624792507922-How-to-manage-API-keys) to learn how to create one. We recommend not to store the API key in the config. You may use [github secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions) or a [local vault](https://github.com/mylofi/local-vault) to keep the key secret.  



## Further Considerations

It is a sort of a philosophical question, whether you want to allow your developers to commit or not. Sometimes it may be more desireable to secure all changes and not prevent commits. In other cases, it may bo of more relevance to keep the code clean and not to allow such obscure commits. Depending on your branching strategy, it might make sense to have different bahviour at different levels. 

We, for example, prefer to work with feature branches. On these feature branches, we allow all commits to simplify life for  developers and prevention of work loss. But we do *not* allow merging into main, as long as the ts-scan has findings.  

