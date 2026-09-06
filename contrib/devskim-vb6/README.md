# DevSkim rule pack for classic Visual Basic 6

[DevSkim](https://github.com/microsoft/DevSkim) is Microsoft's lightweight, regex based
security linter. It ships without any notion of classic Visual Basic 6, but both its
language list and its rule set are plain JSON. This directory adds

* `languages.json` - DevSkim's default language list plus a `vb6` language covering
  `.bas`, `.cls`, `.frm`, `.ctl`, `.pag`, `.dsr`, `.dob`, `.vbp` and `.vbg` files
* `comments.json` - DevSkim's default comment definitions plus the VB6 `'` line comment,
  so that findings inside comments are ignored and `// DevSkim: ignore` style
  suppressions work
* `rules/vb6-security.json` - 22 security rules written for VB6 idioms (see below)

DevSkim's own default rules stay active. Rules without a language restriction, for
example the cleartext `http://` URL and the weak hash algorithm checks, apply to the
new `vb6` language automatically. Where a VB6 rule covers the same ground as a default
rule it declares an `overrides` entry so that a finding is reported once.

The result is a SARIF 2.1 file, which TrustSource, GitHub code scanning, Azure DevOps
and most IDEs can display. This is a first cut: pattern matching finds dangerous API
usage and obvious mistakes, it does not follow data flow. Use it to get a quick picture
of a legacy code base and to seed a manual review, not as a proof of absence.

## Running it

DevSkim is a .NET global or local tool. Install it once:

```bash
dotnet tool install --global Microsoft.CST.DevSkim.CLI
```

Then scan a VB6 source tree and write SARIF:

```bash
devskim analyze -I path/to/vb6/project -O vb6-findings.sarif -f sarif \
  -r contrib/devskim-vb6/rules \
  --languages contrib/devskim-vb6/languages.json \
  --comments contrib/devskim-vb6/comments.json \
  --base-path path/to/vb6/project
```

`--languages` and `--comments` must always be given together; they replace DevSkim's
built-in lists, which is why the files here contain the defaults as well. Use `-f text`
for a quick look in the terminal and `--severity critical,important` to focus on the
serious findings. `scan.sh` in this directory wraps the command above.

Self-tests for every rule are embedded as `must-match` / `must-not-match` samples and
are checked with:

```bash
devskim verify -r contrib/devskim-vb6/rules \
  --languages contrib/devskim-vb6/languages.json \
  --comments contrib/devskim-vb6/comments.json
```

A deliberately insecure sample application that triggers every rule lives in
[`examples/vb6-legacy-insecure`](../../examples/vb6-legacy-insecure/README.md).

## Rules

| Id | Severity | What it looks for |
|----|----------|-------------------|
| TSVB6001 | important | SQL statements assembled by string concatenation (`Execute`, `Recordset.Open`, `CommandText`) |
| TSVB6002 | important | `Shell` with a command line that is not a fixed literal |
| TSVB6003 | important | `WScript.Shell`, `Shell.Application`, `ShellExecute` process execution |
| TSVB6004 | important | Microsoft Script Control `Eval` / `ExecuteStatement` / `AddCode` with runtime script text |
| TSVB6005 | critical | Hard-coded passwords, keys and tokens in constants and connection strings |
| TSVB6006 | moderate | `Persist Security Info=True` in connection strings |
| TSVB6007 | important | MD2/MD4/MD5, RC2/RC4, DES CryptoAPI constants and XOR "encryption" |
| TSVB6008 | moderate | SHA-1 (`CALG_SHA1`) |
| TSVB6009 | important | `Rnd()` near token, password, salt, session or key handling |
| TSVB6010 | moderate | `SendKeys` keystroke injection |
| TSVB6011 | moderate | `On Error Resume Next` |
| TSVB6012 | moderate | `Kill`, `FileCopy`, `RmDir`, `MkDir`, `ChDir`, `Open ... For ...` with a dynamic path |
| TSVB6013 | critical | ServerXMLHTTP / WinHttpRequest configured to ignore TLS certificate errors |
| TSVB6014 | important | MSXML `resolveExternals = True` or `ProhibitDTD = False` (XXE) |
| TSVB6015 | moderate | Winsock control (raw, unencrypted sockets) |
| TSVB6016 | moderate | Internet Transfer Control (MSINET) and `OpenURL` with a dynamic URL |
| TSVB6017 | moderate | `CopyMemory` / `RtlMoveMemory`, `VarPtr` / `StrPtr` / `ObjPtr` usage |
| TSVB6018 | important | Secrets written to or read from the registry via `SaveSetting` / `GetSetting` / `RegSetValueEx` |
| TSVB6019 | manual review | Untrusted input sources: `Command$`, `Environ$`, `InputBox` |
| TSVB6020 | moderate | `LoadLibrary` with a bare DLL name (search order hijacking) |
| TSVB6021 | moderate | References to out-of-support components (MSXML 2/4/5, DAO 3.5, CAPICOM, VB5 runtime, Common Controls 5.0) |
| TSVB6022 | best practice | `Err.Description` shown to the user in a `MsgBox` |

`Declare` statements themselves are not reported for TSVB6003, TSVB6017, TSVB6018 and
TSVB6020; only the call sites are. Rule ids are stable; treat them as the key when
triaging findings.

One DevSkim quirk (observed with 1.0.90) shapes how the rules are written: when a rule
carries `conditions`, only the matches of the first pattern that hits in a file are
reported. Rules with conditions therefore use a single pattern with alternation
instead of several patterns.

## Extending

Copy an existing rule, give it a new `TSVB6nnn` id, add at least one `must-match` and one
`must-not-match` sample and run `devskim verify`. Patterns are .NET regular expressions;
VB6 is case-insensitive, so every pattern carries the `i` modifier. Keep the `scopes`
at `["code"]` so that commented-out code does not produce findings.
