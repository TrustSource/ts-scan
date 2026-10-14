# Conan 2 example

Scan a project using the same profiles, settings, and options as its build:

```shell
.venv/bin/python ./ts-scan scan examples/conan \
  --conan:forward=-pr:h=default,-pr:b=default -o /tmp/conan-scan.json
```

Conan 2 must be installed and its profiles configured. The scanner invokes
`conan graph info`, honoring an existing `conan.lock`, without installing or
building package binaries. Graph resolution executes Conan recipes and may
download recipes from configured remotes. Pass `--conan:forward=--no-remote`
to resolve exclusively from the local Conan cache.

Alternatively, capture the graph in your build and scan it without invoking Conan:

```shell
conan graph info examples/conan --format=json > /tmp/conan-graph.json
.venv/bin/python ./ts-scan scan examples/conan \
  --conan:graphFile /tmp/conan-graph.json -o /tmp/conan-scan.json
```

`graphFile` is resolved relative to the scanner's working directory. Use one
source per invocation with this option; the supplied graph represents that source.
Explicit graph input also supports a source directory without a recipe.

The checked-in `graph.json` is a synthetic test fixture with shared transitive
dependencies, a user/channel reference, a build tool, and a test dependency.
It is deliberately richer than `conanfile.txt` and can be scanned offline:

```shell
.venv/bin/python ./ts-scan scan examples/conan \
  --conan:graphFile examples/conan/graph.json -o /tmp/conan-scan.json
```

Host dependencies are included by default. Add
`--conan:includeBuildDependencies` and/or `--conan:includeTestDependencies`
to include the corresponding dependencies. Skipped edges are omitted.

PURLs preserve user, channel, recipe/package revisions, settings, and options;
additional Conan metadata is retained in `meta.conan` in TrustSource output.
Conan's recipe `url` maps to `repoUrl`, which may identify the recipe repository
rather than the upstream source repository. Recipe revisions and package IDs are
not treated as archive checksums. System libraries and Python recipe requirements
remain metadata, rather than being represented as resolved Conan packages.

Resolution failures or invalid graph files report an incomplete scan and produce
no Conan scan. Conan 1 graphs and lockfile-only scanning are not supported.
