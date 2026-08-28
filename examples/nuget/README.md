# NuGet solution hierarchy example

This small solution exercises project hierarchy handling and a resolved package
dependency from NuGet.org:

```text
ExampleSolution
├── Example.App
│   ├── Example.Core
│   └── NLog 5.3.0
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
