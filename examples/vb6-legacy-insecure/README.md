# OrderDesk - a deliberately insecure Visual Basic 6 application

`OrderDesk` is a small, fictitious order management client written the way a lot of
VB6 code in production still looks: ADO against SQL Server, a handful of Microsoft
ActiveX controls, some Win32 `Declare`s and a few shortcuts taken in 2001 that nobody
has revisited since. **Every file contains at least one security problem on purpose.**
Do not copy anything from it into real code.

It exists to demonstrate two things ts-scan can do with legacy VB6 code:

1. **Build an SBOM from the project file.** `ts-scan scan` reads `OrderDesk.vbp` and
   reports every COM reference, ActiveX control, native library and the implicit VB6
   runtime, enriched with vendor, title, life-cycle notes and known advisories from
   ts-scan's VB6 catalogue.
2. **Produce SARIF security findings** with the DevSkim rule pack in
   [`contrib/devskim-vb6`](../../contrib/devskim-vb6/README.md).

## SBOM

```bash
ts-scan scan -o orderdesk.json examples/vb6-legacy-insecure/OrderDesk/OrderDesk.vbp
```

or, for a CycloneDX document:

```bash
ts-scan scan -f cyclonedx-json -o orderdesk.cdx.json examples/vb6-legacy-insecure/OrderDesk/OrderDesk.vbp
```

The scan reports the module `vb:OrderDesk` (version 2.4.17) with these components:

| Component | Source in project | Catalogue note |
|-----------|-------------------|----------------|
| `lib:tlb:stdole2` | `Reference=` | OLE Automation |
| `lib:tlb:msado28` | `Reference=` | Microsoft ActiveX Data Objects 2.8 |
| `lib:dll:scrrun` | `Reference=` | Microsoft Scripting Runtime |
| `lib:dll:msxml4` | `Reference=` | MSXML 4.0, support ended April 2014 |
| `lib:ocx:msscript` | `Reference=` | Script Control, executes dynamic script |
| `lib:dll:PriceEngine` | `Reference=` | third-party DLL, not in the catalogue |
| `lib:ocx:MSCOMCTL` | `Object=` | Common Controls 6.0, advisories CVE-2012-0158 and CVE-2012-1856 |
| `lib:ocx:MSWINSCK` | `Object=` | Winsock control, unencrypted sockets |
| `lib:ocx:MSINET` | `Object=` | Internet Transfer Control, legacy HTTP client |
| `lib:ocx:COMDLG32` | `Object=` | Common Dialog control |
| `lib:dll:shell32`, `lib:dll:advapi32`, `lib:dll:kernel32` | `Declare` statements | Windows system libraries |
| `lib:dll:MSVBVM60` | implicit | Visual Basic 6.0 runtime |

## Security findings

```bash
contrib/devskim-vb6/scan.sh examples/vb6-legacy-insecure/OrderDesk orderdesk.sarif
```

What each file demonstrates:

| File | Problems built in |
|------|-------------------|
| `frmLogin.frm` | hard-coded emergency password, SQL injection in the login query, `On Error Resume Next` around authentication, `Err.Description` shown to the user, last password stored in the registry |
| `frmMain.frm` | cleartext `http://` default URL, order number passed straight into a `DELETE` statement, `Environ$` as audit identity |
| `modDb.bas` | connection string with `sa` password and `Persist Security Info=True`, four concatenated SQL statements |
| `modShell.bas` | `Shell` with a user supplied file name, `WScript.Shell`, `ShellExecute`, `Kill` with a dynamic path, `SendKeys` typing credentials, `Command$` / `Environ$` input |
| `modCrypto.bas` | MD5 password hash, RC4 with an MD5 derived key, DES constant, XOR "encryption", `Rnd()` session token, hard-coded license key |
| `modNet.bas` | TLS certificate errors ignored in ServerXMLHTTP, plain HTTP price service, Winsock traffic, MSXML 4.0 with `resolveExternals = True` (XXE) |
| `modApi.bas` | `CopyMemory` on a raw pointer, `LoadLibrary "PriceEngine.dll"` without a path |
| `modScript.bas` | Script Control `Eval` / `ExecuteStatement` on rule text from the database |
| `clsAuditLog.cls` | log file path built from the user name, `On Error Resume Next` |
| `OrderDesk.vbp` | references to MSXML 4.0, Winsock and Internet Transfer controls |

The project does not include any binaries. It cannot be compiled as is because the
referenced third-party `PriceEngine.dll` does not exist, which is intentional: the
point is the scan, not the build.
