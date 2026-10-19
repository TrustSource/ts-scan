# vcpkg scanning

Scan a vcpkg project without special options:

```shell
.venv/bin/python ./ts-scan scan examples/vcpkg -o /tmp/vcpkg-scan.json
```

The scanner discovers existing package data automatically. When a project has a
`vcpkg.json` but no package database, it runs `vcpkg install` to resolve and install
the manifest dependencies, then scans the resulting data. This can download and
build packages. vcpkg uses its configured registry, baseline, default triplet, and
manifest features. An existing snapshot can be scanned without a vcpkg executable.
No additional Python dependencies are required.

This directory contains synthetic fixtures, not installed upstream software.
The fixture demonstrates an ARM64 target, x64 build tools, a feature dependency,
shared dependencies, a private registry, an unrelated installed port, and pending
updates which upgrade zlib and remove another package.

```shell
.venv/bin/python ./ts-scan scan examples/vcpkg \
  --vcpkg:installedDir examples/vcpkg/installed \
  --vcpkg:triplet arm64-linux \
  --vcpkg:roots curl --vcpkg:roots libpng \
  -o /tmp/vcpkg-scan.json
```

For a custom installation or a specific build configuration, override discovery:

```shell
.venv/bin/python ./ts-scan scan /path/to/project \
  --vcpkg:installedDir /path/to/build/vcpkg_installed \
  --vcpkg:triplet x64-linux --vcpkg:roots curl \
  -o /tmp/vcpkg-scan.json
```

Discovery honors `VCPKG_INSTALLED_DIR`, then checks the source itself,
`<source>/vcpkg_installed`, and `<source>/installed`. It also discovers CMake
installation paths from `CMakeCache.txt` in standard `build`, `build/<config>`,
`cmake-build*`, and `out/build/<config>` folders, and their `vcpkg_installed`
subdirectories. Multiple build installations require `installedDir` to select
one rather than mix their configurations. A manifest project does not reuse an
unrelated global classic installation.

For classic projects, vcpkg's root is discovered from `VCPKG_ROOT`, the CMake
toolchain, the executable, a nearby vcpkg checkout, or conventional home checkout
locations. Its `installed` directory is then used. The installation directory
itself can also be passed as the source. A vcpkg checkout requires its standard
`.vcpkg-root` marker for automatic root discovery (an explicit `VCPKG_ROOT` is
respected directly). Installing only the Homebrew vcpkg binary does not provide
a port checkout; vcpkg's own diagnostic is shown if its root is unconfigured.

`installedDir` is resolved relative to the scanner's working directory. Supplying
it selects a read-only snapshot and disables automatic installation. Use
`--vcpkg:noInstall` to allow discovery but disable installation. For unusual tool
setups use `--vcpkg:executable` or `--vcpkg:forward`; forwarded arguments reach the
install command. For example, `--vcpkg:forward=--x-feature=tests` selects an
additional manifest feature during installation. Existing snapshots retain their
installed features; changing forwarded resolution options does not rebuild them.

`roots` is repeatable. With `triplet`, roots may be bare port names; without it,
each root must be qualified, such as `--vcpkg:roots curl:arm64-linux`.
The scanner follows the installed dependencies, including dependencies from all
installed features and cross-triplet build tools. The triplet option selects
roots, not their transitive closure. Host/tool dependencies are included; their
role cannot reliably be inferred from installed records alone.

Without explicit roots, the result is an **installed-package inventory** of all
ports in the selected triplet, or all triplets if none is selected. A shared
installation may contain unrelated packages and extra installed features; the
result is not a claim about which libraries the application links or ships.
Even a root-scoped scan reflects installed features, not a fresh manifest
resolution. The manifest supplies project identity and is retained as metadata;
platform expressions and feature selection are evaluated by vcpkg when installing.

The scanner replays `vcpkg/status` and completed files in `vcpkg/updates` in
filename order, leaving them untouched. `incomplete` is ignored. Removed and
half-installed records are excluded. Missing core records, unresolved dependency
targets, malformed databases, or invalid roots produce a warning and no vcpkg
scan. Scan after the build/install finishes; concurrent database writes are not
supported. Missing installation data triggers installation only for manifest
projects using automatic discovery, unless `noInstall` is set.

Package SPDX files under `<installedDir>/<triplet>/share/<port>/vcpkg.spdx.json`
enrich the graph. The scanner reads the port record, preserves full license
expressions and PURL registry provenance, and retains source-resource records in
`meta.vcpkg`. Upstream version, port revision, and binary ABI remain separate.
ABI hashes are not archive checksums. Missing, malformed, or stale SPDX metadata
keeps the resolved graph but emits warnings, also recorded on the root with
`metadata_complete: false`. Copyright paths are retained for later analysis;
license text analysis is not invoked automatically.

Use `--vcpkg:ignore` to disable detection. Existing `--format` options export to
TrustSource, CycloneDX, or SPDX; extra `meta.vcpkg` fields are retained in
TrustSource output. Module IDs distinguish root-scoped scans from inventories
and include an explicitly selected triplet. Use a consistent root selection for
each module in CI.

The relevant upstream formats are documented in the
[vcpkg SBOM guide](https://learn.microsoft.com/en-us/vcpkg/reference/software-bill-of-materials)
and [vcpkg PURL definition](https://github.com/package-url/purl-spec/blob/main/types/vcpkg-definition.json).
