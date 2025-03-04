# Adding Features

We highly apperaciate any kind of support in enhancing the capabilities further. On our current roadmap you may see, how our priorities are aligned. 

> [!IMPORTANT]
>
> PLEASE NOTE: To simplify integration of additional featurs, we have provided a short summary of how to add additional capabiliities in the following section as well as a few guidelines on how we want the code to be developed. See the [guidelines](/ts-scan/guidelines.md) for details. 

## 1. Decide where to add 

Before you start adding, decide on where you want to add featurs. Are you planning to add an additional **ecosystem**, e.g. PHP or C#? then you should add this to **ts-scan** itself. Are you instead planning to add something that will work on the **file**-level, then you amy prefer to add to **ts-deepscan**, the integrated file handler.

Please also have a look at the roadmap to get an idea on what is already planned, so that we do not waste resources in implementuing things twice.

Given, you made these decisions, you may start.  

## 2. Be aware of the liecense

We expect all contributions to follow the Apache-2.0 licensing schema. It is simple, safe and straight forward. It ensures freedom to use withoutt the demand to prescribe what you will do with it. 

> [!IMPORTANT]
>
> PLEASE NOTE: We publish all our solutions under the Apache-2.0 license. Some licenses may not comply with licensing under Apache-2.0. We will check pull requests and might return to you in case we will find non-compliantly licensed components or snippets.

By submitting a Pull Reuest we assume that you will confirm your agreement with the licensing your contribution under Apache-2.0 as well. 

## 3. Submitting Issues

We are happy to receive useful information supporting us in improving our tooling. So feel free to open issues in the corresponding section of [this repository](https://github.com/trustsource/ts-scan/issues) or the [deepscan repository](https://github.com/trustsource/ts-deepscan/issues). We will try our best to close the bugs accordingly. 

When submitting a bug, please ensure that you provide us with 

- Version of tools you were using
- Version of Python used in your environment
- Information on how to reproduce the bug, e.g.:
  steps followed, expected bahviour, actual baheviour, further relevant information and/or logs

Thank you!

## 4. Submitting Vulnerabilities

If you see or experience something that may impact the confidentiality, Integrity or availability of our TrustSource solution or the APIs of any our partners, please let us know. For such cases ***please refrain from opening a public issue!***

For such cases please see our *[Security Policy](/ts-scsan/vulns.md)* for information on how to confidentially submit vulnerabilities.

## 5. Submitting Code

We appreciate all sort of support. So, if you are willing to develop a feature that you think could be useful, feel free to discuss with us in advance. However, even if you prefer to just push the code, please follow the [coding gudelines.](/ts-scan/guidelines.md)

To create a pull request, please

- clone the repo
- create a branch for your work, e.g. `fix-issue-123` or `feature/your-feature`
- allow us to follow your work by providing friendly commit messages
- test thoroughly and do not forget to provide the tests in case you added functionality
- commit the reuest stating
  * why it has been introduced 
  * what it tries to achieve and how
  * the dependencies added
  * prevent your editor from reformatting, so that we may understand the changes
- be patient, we try to review and retrun as soon as possible. 

**Thank you in advance for your support!!!**
