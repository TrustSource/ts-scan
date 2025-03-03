# Use Case #01 - Auto Scan on Commit

One of the most relevant cases for **ts-scan** is to be executed whenever new code is about to be commited. 

## Why you would want to do this?

The earlier you identify odd code, the less expensive will be the repair, taking the sunk costs of having put the wrong solution into place. All the integration work, all the testing could have been saved when your Developers would have knwon the impact *before* they added the particular library. TrustSource provide a [CHECK](/ts-scan/index) verb to test particular libraries, components or files form the CLI before adding them. 

However, whether this will always be done when time is calling is a different thing. But the very first step you may start ensuring that your developers will take the verification requirement serious is, when you require them to pass a successful verification upon checkin, e.g. using [pre-commit](https://pre-commit.com).

This will prevent your developers from commiting dependencies with known vulnerbailities (or weak crypto algorithms, or bad licenses, etc.)

## Prerequisites

The first step is to setup pre-commit, see [here](https://pre-commit.com/#install) for more detauls. Pre-commit will perform tests *before* the code is accepted as a commit to the repository. 

> [!NOTE]
>
> You also may decide to include this action into a Git-Workflow, e.g. when the build action is part of an automated CI/CD-chain waiting for the next commit. This also would work. The difference to our suggestion is that *pre-commit* prevents the unwanted extension to enter the repository.  

Please clarify the intended behaviour within your developer community first. See below for further thoughts.

## Steps to Success

After having installed pre-commit, amend the `.pre-commit.yml` file as follows:

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

## Further Considerations

It is a sort of a philosophical question, whether you want to allow your developers to commit or not. Sometimes it may be more wanted to secure all changes and not prevent commits. In other cases, it may bo of more relevance to keep the code clean and not allow commits. Depending on your branching strategy, it might make sense to have different bahviour on different levels. 

We for example, prefer to work with feature branches. On these feature branches, we allow all commits to simplify life for a developer and prevent loss of work. We do *not* allow merging into main, as long as the ts-scan has findings.  

## Related Topics

