# NuGet solution hierarchy example

This small solution exercises project hierarchy handling without external package feeds:

```text
ExampleSolution
├── Example.App
│   └── Example.Core
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

Or scan one project:

```console
ts-scan scan examples/nuget/Legacy.Core/Legacy.Core.csproj
```
