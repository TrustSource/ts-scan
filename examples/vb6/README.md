# Visual Basic 6 project-group example

This example represents a typical VB6 application group with an executable and
an in-house ActiveX DLL project:

```text
LegacySuite
├── InventoryCore (`vb:InventoryCore`)
└── InventoryApp (`vb:InventoryApp`)
    ├── InventoryCore (`vb:InventoryCore`)
    ├── LegacyReports (`lib:dll:LegacyReports`)
    ├── MSCOMCTL (`lib:ocx:MSCOMCTL`)
    └── user32 (`lib:dll:user32`)
```

`InventoryCore` is recognized as a project reference because its
`ExeName32=InventoryCore.dll` output matches the DLL path referenced by
`Inventory.App.vbp`. `LegacyReports.dll` and `MSCOMCTL.OCX` demonstrate external
VB6 `Reference` and `Object` entries. `user32.dll` demonstrates a native import
declared in a `.bas` source file.

The example does not include the proprietary/system binaries. When a referenced
binary exists at its relative path, the scanner includes its resolved location
in `package_files`.

Scan the project group:

```console
ts-scan scan examples/vb6/LegacySuite.vbg
```

Or scan one project:

```console
ts-scan scan examples/vb6/Inventory.App/Inventory.App.vbp
```
