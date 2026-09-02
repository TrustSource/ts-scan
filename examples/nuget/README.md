# NuGet solution hierarchy example

This small solution exercises project hierarchy handling and a resolved package
dependency from NuGet.org:

```text
ExampleSolution
├── Example.App
│   ├── Example.Core
│   ├── NLog 5.3.0
│   └── Example.Native 2.1.0.0 (`lib:dll:Example.Native`)
├── Example.Core
│   └── Example.Shared
└── Example.Shared
```

`Legacy.Core.csproj` deliberately uses `Example.Core` as its `PackageId`, and
`Shared.csproj` uses `Example.Shared`. This verifies that scan identities come
from NuGet/MSBuild metadata rather than directory or project filenames alone.

Scan the whole solution:

```console
ts-scan scan examples/nuget/ExampleSolution.sln
```

The resulting scan should contain `NLog` version `5.3.0` below `Example.App`.
It also contains the file-backed MSBuild assembly reference as
`lib:dll:Example.Native`, with its `HintPath`, assembly identity, source project,
and copy-local setting in dependency metadata. The referenced DLL is
intentionally not included in this source example; when the file exists, its
resolved path is also added to `package_files`.

Or scan one project:

```console
ts-scan scan examples/nuget/Legacy.Core/Legacy.Core.csproj
```

## Try the project.assets.json fallback

First restore the solution with the .NET SDK. This creates each project's
`obj/project.assets.json`:

```console
dotnet restore examples/nuget/ExampleSolution.sln
```

On macOS with Mono installed, use `msbuild` instead:

```console
msbuild examples/nuget/ExampleSolution.sln /t:Restore
```

Remove the generated lockfiles while retaining the `obj` directories:

```console
find examples/nuget -name packages.lock.json -delete
```

On macOS, use `/usr/bin/true` as a harmless stand-in for the restore command.
It exits successfully without creating `packages.lock.json`, deterministically
reproducing the condition that activates the fallback:

```console
ts-scan scan --nuget:executable /usr/bin/true examples/nuget/ExampleSolution.sln
```

The scanner should report that it is using resolved dependencies from
`project.assets.json`, and `NLog` version `5.3.0` should still be present in the
scan.
