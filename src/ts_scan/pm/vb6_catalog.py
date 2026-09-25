"""Catalogue of well-known libraries referenced by classic Visual Basic 6 projects.

VB6 project files reference COM type libraries, ActiveX controls and native DLLs
by file name only. This catalogue attaches vendor, title and life-cycle notes to
the most common ones so that scan results are readable without a Windows box at
hand. Entries are keyed by the lower-case file name including its extension
(``mscomctl.ocx``); native ``Declare`` statements without an extension are
looked up as ``.dll``.

The catalogue is intentionally conservative: it only lists facts that are
stable (vendor, product title, category, well-known end-of-support and
advisory information). Vulnerability matching itself remains the job of the
TrustSource platform.
"""

import typing as t

CATEGORY_RUNTIME = 'runtime'
CATEGORY_ACTIVEX_CONTROL = 'activex-control'
CATEGORY_COM_LIBRARY = 'com-library'
CATEGORY_TYPE_LIBRARY = 'type-library'
CATEGORY_WINDOWS_SYSTEM = 'windows-system'

MICROSOFT = 'Microsoft'

#: File name of the Visual Basic 6 runtime every VB6 output depends on.
VB6_RUNTIME_FILE = 'msvbvm60.dll'
VB6_RUNTIME_VERSION = '6.0'


class _CatalogEntryBase(t.TypedDict):
    title: str
    vendor: str
    category: str


class CatalogEntry(_CatalogEntryBase, total=False):
    notes: str
    advisories: t.List[str]


def _entry(title: str, category: str, notes: str = '',
           advisories: t.Optional[t.List[str]] = None,
           vendor: str = MICROSOFT) -> CatalogEntry:
    entry: CatalogEntry = {'title': title, 'vendor': vendor, 'category': category}
    if notes:
        entry['notes'] = notes
    if advisories:
        entry['advisories'] = list(advisories)
    return entry


_VB6_IDE_EOL = (
    'Extended support for the Visual Basic 6.0 IDE ended on 2008-04-08; '
    'the runtime is only supported on currently supported Windows versions.'
)

CATALOG: t.Dict[str, CatalogEntry] = {
    # --- runtimes ------------------------------------------------------------
    'msvbvm60.dll': _entry('Microsoft Visual Basic 6.0 Runtime', CATEGORY_RUNTIME, _VB6_IDE_EOL),
    'msvbvm50.dll': _entry('Microsoft Visual Basic 5.0 Runtime', CATEGORY_RUNTIME,
                           'Visual Basic 5.0 is out of support.'),
    'msvcrt.dll': _entry('Microsoft C Runtime Library', CATEGORY_WINDOWS_SYSTEM),

    # --- ActiveX controls shipped with Visual Basic 6 ----------------------------
    'mscomctl.ocx': _entry(
        'Microsoft Windows Common Controls 6.0 (SP6)', CATEGORY_ACTIVEX_CONTROL,
        'Historically affected by remote code execution flaws; keep the SP6 '
        'security update level.',
        advisories=['CVE-2012-0158', 'CVE-2012-1856'],
    ),
    'comctl32.ocx': _entry('Microsoft Windows Common Controls 5.0 (SP2)', CATEGORY_ACTIVEX_CONTROL,
                           'Superseded by MSCOMCTL.OCX (Common Controls 6.0).'),
    'mscomct2.ocx': _entry('Microsoft Windows Common Controls-2 6.0', CATEGORY_ACTIVEX_CONTROL),
    'comdlg32.ocx': _entry('Microsoft Common Dialog Control 6.0', CATEGORY_ACTIVEX_CONTROL),
    'msflxgrd.ocx': _entry('Microsoft FlexGrid Control 6.0', CATEGORY_ACTIVEX_CONTROL),
    'mshflxgd.ocx': _entry('Microsoft Hierarchical FlexGrid Control 6.0', CATEGORY_ACTIVEX_CONTROL),
    'mswinsck.ocx': _entry('Microsoft Winsock Control 6.0', CATEGORY_ACTIVEX_CONTROL,
                           'Raw TCP/UDP sockets without transport encryption.'),
    'msinet.ocx': _entry('Microsoft Internet Transfer Control 6.0', CATEGORY_ACTIVEX_CONTROL,
                         'Legacy HTTP/FTP client without modern TLS configuration.'),
    'mscomm32.ocx': _entry('Microsoft Comm Control 6.0', CATEGORY_ACTIVEX_CONTROL),
    'richtx32.ocx': _entry('Microsoft Rich Textbox Control 6.0', CATEGORY_ACTIVEX_CONTROL),
    'tabctl32.ocx': _entry('Microsoft Tabbed Dialog Control 6.0', CATEGORY_ACTIVEX_CONTROL),
    'msmask32.ocx': _entry('Microsoft Masked Edit Control 6.0', CATEGORY_ACTIVEX_CONTROL),
    'msdatgrd.ocx': _entry('Microsoft DataGrid Control 6.0 (OLEDB)', CATEGORY_ACTIVEX_CONTROL),
    'msdatlst.ocx': _entry('Microsoft DataList Controls 6.0 (OLEDB)', CATEGORY_ACTIVEX_CONTROL),
    'msadodc.ocx': _entry('Microsoft ADO Data Control 6.0 (OLEDB)', CATEGORY_ACTIVEX_CONTROL),
    'mschrt20.ocx': _entry('Microsoft Chart Control 6.0 (OLEDB)', CATEGORY_ACTIVEX_CONTROL),
    'msscript.ocx': _entry('Microsoft Script Control 1.0', CATEGORY_ACTIVEX_CONTROL,
                           'Executes dynamically supplied VBScript/JScript code.'),
    'sysinfo.ocx': _entry('Microsoft SysInfo Control 6.0', CATEGORY_ACTIVEX_CONTROL),
    'picclp32.ocx': _entry('Microsoft PictureClip Control 6.0', CATEGORY_ACTIVEX_CONTROL),
    'dbgrid32.ocx': _entry('Microsoft Data Bound Grid Control 5.0 (SP3)', CATEGORY_ACTIVEX_CONTROL),
    'msstdfmt.dll': _entry('Microsoft Data Formatting Object Library 6.0', CATEGORY_COM_LIBRARY),

    # --- COM libraries and type libraries -----------------------------------------
    'stdole2.tlb': _entry('OLE Automation', CATEGORY_TYPE_LIBRARY),
    'stdole32.tlb': _entry('OLE Automation', CATEGORY_TYPE_LIBRARY),
    'oleaut32.dll': _entry('OLE Automation', CATEGORY_WINDOWS_SYSTEM),
    'msado15.dll': _entry('Microsoft ActiveX Data Objects (ADO)', CATEGORY_COM_LIBRARY),
    'msadox.dll': _entry('Microsoft ADO Ext. for DDL and Security', CATEGORY_COM_LIBRARY),
    'msadomd.dll': _entry('Microsoft ActiveX Data Objects (Multi-dimensional)', CATEGORY_COM_LIBRARY),
    'msador15.dll': _entry('Microsoft ActiveX Data Objects Recordset', CATEGORY_COM_LIBRARY),
    'dao350.dll': _entry('Microsoft DAO 3.51 Object Library', CATEGORY_COM_LIBRARY,
                         'Jet 3.5 data access, 32-bit only, out of support.'),
    'dao360.dll': _entry('Microsoft DAO 3.6 Object Library', CATEGORY_COM_LIBRARY,
                         'Jet 4.0 data access, 32-bit only.'),
    'scrrun.dll': _entry('Microsoft Scripting Runtime', CATEGORY_COM_LIBRARY,
                         'FileSystemObject and Dictionary.'),
    'vbscript.dll': _entry('Microsoft VBScript Regular Expressions', CATEGORY_COM_LIBRARY,
                           'VBScript is deprecated and being removed from Windows.'),
    'msxml.dll': _entry('Microsoft XML 2.0', CATEGORY_COM_LIBRARY, 'Out of support.'),
    'msxml2.dll': _entry('Microsoft XML 2.6', CATEGORY_COM_LIBRARY, 'Out of support.'),
    'msxml3.dll': _entry('Microsoft XML 3.0 (MSXML3)', CATEGORY_COM_LIBRARY),
    'msxml4.dll': _entry('Microsoft XML 4.0 (MSXML4)', CATEGORY_COM_LIBRARY,
                         'MSXML 4.0 SP3 support ended in April 2014.'),
    'msxml5.dll': _entry('Microsoft XML 5.0 (MSXML5, Office)', CATEGORY_COM_LIBRARY, 'Out of support.'),
    'msxml6.dll': _entry('Microsoft XML 6.0 (MSXML6)', CATEGORY_COM_LIBRARY),
    'shdocvw.dll': _entry('Microsoft Internet Controls (WebBrowser)', CATEGORY_COM_LIBRARY,
                          'Internet Explorer based WebBrowser control.'),
    'ieframe.dll': _entry('Microsoft Internet Controls (WebBrowser)', CATEGORY_COM_LIBRARY,
                          'Internet Explorer based WebBrowser control.'),
    'capicom.dll': _entry('Microsoft CAPICOM', CATEGORY_COM_LIBRARY,
                          'Deprecated cryptography component, no longer shipped.'),
    'msscript.dll': _entry('Microsoft Script Control', CATEGORY_COM_LIBRARY),
    'wshom.ocx': _entry('Windows Script Host Object Model', CATEGORY_COM_LIBRARY,
                        'Provides WScript.Shell process execution.'),
    'shell32.dll': _entry('Microsoft Shell Controls and Automation', CATEGORY_WINDOWS_SYSTEM),

    # --- native Windows system libraries commonly used through Declare -------------
    'kernel32.dll': _entry('Windows NT BASE API Client', CATEGORY_WINDOWS_SYSTEM),
    'user32.dll': _entry('Windows USER API Client', CATEGORY_WINDOWS_SYSTEM),
    'gdi32.dll': _entry('Windows GDI Client', CATEGORY_WINDOWS_SYSTEM),
    'advapi32.dll': _entry('Windows Advanced API (registry, security, CryptoAPI)', CATEGORY_WINDOWS_SYSTEM),
    'ole32.dll': _entry('Microsoft OLE for Windows', CATEGORY_WINDOWS_SYSTEM),
    'comctl32.dll': _entry('Windows Common Controls Library', CATEGORY_WINDOWS_SYSTEM),
    'comdlg32.dll': _entry('Windows Common Dialogs', CATEGORY_WINDOWS_SYSTEM),
    'shlwapi.dll': _entry('Windows Shell Light-weight Utility Library', CATEGORY_WINDOWS_SYSTEM),
    'wininet.dll': _entry('Windows Internet Extensions', CATEGORY_WINDOWS_SYSTEM),
    'winhttp.dll': _entry('Windows HTTP Services', CATEGORY_WINDOWS_SYSTEM),
    'urlmon.dll': _entry('OLE32 Extensions for Win32 (URL Moniker)', CATEGORY_WINDOWS_SYSTEM),
    'ws2_32.dll': _entry('Windows Sockets 2.0', CATEGORY_WINDOWS_SYSTEM),
    'wsock32.dll': _entry('Windows Sockets 1.1', CATEGORY_WINDOWS_SYSTEM),
    'winmm.dll': _entry('Windows Multimedia API', CATEGORY_WINDOWS_SYSTEM),
    'crypt32.dll': _entry('Windows Crypto API32', CATEGORY_WINDOWS_SYSTEM),
    'ntdll.dll': _entry('Windows NT Layer', CATEGORY_WINDOWS_SYSTEM),
    'version.dll': _entry('Windows Version Checking and File Installation', CATEGORY_WINDOWS_SYSTEM),
    'mpr.dll': _entry('Windows Multiple Provider Router', CATEGORY_WINDOWS_SYSTEM),
    'netapi32.dll': _entry('Windows Net Win32 API', CATEGORY_WINDOWS_SYSTEM),
    'psapi.dll': _entry('Windows Process Status Helper', CATEGORY_WINDOWS_SYSTEM),
    'winspool.drv': _entry('Windows Spooler Driver', CATEGORY_WINDOWS_SYSTEM),
    'imm32.dll': _entry('Windows Input Method Manager', CATEGORY_WINDOWS_SYSTEM),
    'msimg32.dll': _entry('Windows GDI+ Image Helper', CATEGORY_WINDOWS_SYSTEM),
    'gdiplus.dll': _entry('Microsoft GDI+', CATEGORY_WINDOWS_SYSTEM),
}

# ADO ships one type library per version (msado20.tlb ... msado28.tlb).
for _minor in ('20', '21', '25', '26', '27', '28'):
    CATALOG[f'msado{_minor}.tlb'] = _entry(
        f'Microsoft ActiveX Data Objects {_minor[0]}.{_minor[1]} Library',
        CATEGORY_TYPE_LIBRARY,
    )


def lookup(name: str, library_type: str) -> t.Optional[CatalogEntry]:
    """Return the catalogue entry for ``name`` with the given file type, if any."""
    file_name = f'{name}.{library_type}'.casefold() if library_type else name.casefold()
    return CATALOG.get(file_name)
