# Use Case #04 - SBOM Generation for npm Monorepos

Many modern Node.js projects use npm workspaces to organise multiple packages inside a single repository. While **ts-scan** handles individual packages out of the box, scanning a monorepo requires a slightly different approach to produce accurate, per-package SBOMs.

## Why you would want to do this?

A monorepo typically contains several packages — for example a backend, a frontend, and a shared library — each with its own `package.json` and dependency tree. Running **ts-scan** against the repository root would attempt to resolve all packages at once, which leads to problems:

- **Workspace symlinks** inside `node_modules` point to sibling packages rather than real dependencies. ts-scan may fail or produce incomplete results when encountering these.
- **A single SBOM for the entire repo** does not reflect which dependencies belong to which deployable artefact. When a vulnerability is found, you cannot tell whether it affects the backend, the frontend, or both.
- **Operational impact** becomes unclear. A per-package SBOM lets you trace a CVE to a specific deployment unit and patch only what is affected.

## Prerequisites

You need **ts-scan** installed (via `pip install ts-scan`) and a CI environment that supports matrix builds, such as GitHub Actions. Each package must have its own `package.json` (and ideally a `package-lock.json`).

> [!NOTE]
>
> ts-scan reads `package.json` and lockfiles directly — it does **not** require `node_modules` to be installed. In fact, running `npm install` inside a workspace package without the root context will fail on `workspace:*` references. Simply skip the install step.

## Steps to Success

Create a GitHub Actions workflow that iterates over your packages using a matrix strategy. Each matrix job scans one package and uploads its SBOM independently:

```yaml
name: SBOM

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  sbom:
    name: SBOM — ${{ matrix.package }}
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        package:
          - backend
          - frontend
          - shared

    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-python@v6
        with:
          python-version: '3.12'

      - name: Install ts-scan
        run: pip install ts-scan

      - name: Scan dependencies & generate SBOM
        run: |
          ts-scan scan \
            --output sbom-${{ matrix.package }}.json \
            packages/${{ matrix.package }}

      - name: Upload SBOM to TrustSource
        run: |
          ts-scan upload \
            --api-key "${{ secrets.TS_API_KEY }}" \
            --project-name "MY_PROJECT" \
            sbom-${{ matrix.package }}.json
```

This will run one job per package in parallel. Each job checks out the repository, installs ts-scan, scans the specific package directory, and uploads the resulting SBOM to TrustSource.

> [!NOTE]
>
> Adjust the `matrix.package` list and the `packages/` path prefix to match your repository layout. The package directories must each contain a `package.json`. If your monorepo uses a different folder structure (e.g. `apps/` and `libs/`), update the paths accordingly.

## Common Pitfalls

**Do not run `npm install` before scanning.** In a workspace monorepo, `npm install` from a subdirectory cannot resolve `workspace:*` references without the root `package.json` context. Since ts-scan parses the package manifest and lockfile directly, installing dependencies is unnecessary and will likely break the workflow.

**Do not scan the repository root.** Running `ts-scan scan .` on a monorepo root will pick up workspace symlinks in `node_modules` and may produce incorrect or duplicate entries. Always point ts-scan at individual package directories.

**Do not use a single SBOM for all packages.** While technically possible by merging results, a single SBOM defeats the purpose of knowing which deployment unit is affected by a vulnerability.

## Further Considerations

This pattern works with any number of packages. As your monorepo grows, simply add entries to the matrix. The jobs run in parallel, so adding more packages does not significantly increase total pipeline time.

If your packages share a common base of dependencies (e.g. TypeScript, a test framework), those will appear in each package's SBOM individually. This is intentional — each SBOM should represent the complete dependency tree of its deployment unit, not a delta.

For monorepos that also contain non-Node.js artefacts (e.g. Terraform modules, Python scripts), you can extend the matrix with additional entries and use the appropriate ts-scan scanner for each technology.
