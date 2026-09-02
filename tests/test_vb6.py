import shutil
from pathlib import Path

import ts_scan

from ts_scan.pm.vb6 import VB6Scanner


EXAMPLE = Path(__file__).parents[1] / 'examples' / 'vb6'


def test_accepts_vb6_projects_and_groups(tmp_path):
    scanner = VB6Scanner()

    assert scanner.accepts(tmp_path) is False
    project = tmp_path / 'Example.VBP'
    project.write_text('Type=Exe\nName="Example"\n')
    assert scanner.accepts(project) is True
    assert scanner.accepts(tmp_path) is True
    group = tmp_path / 'Example.VBG'
    group.write_text('VBG=VBG\nProject=Example.VBP\n')
    assert scanner.accepts(group) is True


def test_group_scan_maps_projects_and_external_libraries(tmp_path):
    example = tmp_path / 'vb6'
    shutil.copytree(EXAMPLE, example)
    scanner = VB6Scanner()

    scan = scanner.scan(example / 'LegacySuite.vbg')[0]

    assert scan.module == 'LegacySuite'
    assert scan.moduleId == 'vb:LegacySuite'
    assert [dependency.key for dependency in scan.dependencies] == [
        'vb:InventoryCore',
        'vb:InventoryApp',
    ]
    assert scan.dependencies[0].versions == ['1.2.0']
    app = scan.dependencies[1]
    assert app.versions == ['3.0.5']
    assert [dependency.key for dependency in app.dependencies] == [
        'vb:InventoryCore',
        'lib:dll:LegacyReports',
        'lib:ocx:MSCOMCTL',
        'lib:dll:user32',
    ]

    project_reference = app.dependencies[0]
    assert project_reference.meta['dependency_type'] == 'project'
    assert project_reference.meta['reference']['guid'] == (
        '{11111111-1111-4111-8111-111111111111}'
    )

    reports = app.dependencies[1]
    assert reports.namespace == 'dll'
    assert reports.versions == ['4.0']
    assert reports.meta['references'][0]['display_name'] == 'Legacy Reports API'

    native = app.dependencies[3]
    assert native.meta['references'] == [{
        'reference_type': 'declare',
        'path': 'user32.dll',
        'source_file': str((example / 'Inventory.App' / 'NativeApi.bas').resolve()),
        'procedure': 'MessageBox',
        'procedure_type': 'function',
        'scope': 'public',
        'alias': 'MessageBoxA',
    }]


def test_existing_relative_library_is_added_to_package_files(tmp_path):
    project = tmp_path / 'Example.vbp'
    library = tmp_path / 'vendor' / 'Legacy.dll'
    library.parent.mkdir()
    library.write_bytes(b'fixture')
    project.write_text(
        'Type=Exe\n'
        'Reference=*\\G{AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}'
        '#2.5#0#vendor\\Legacy.dll#Legacy API\n'
        'Name="Example"\n'
    )

    scan = VB6Scanner().scan(project)[0]

    assert [dependency.key for dependency in scan.dependencies] == [
        'lib:dll:Legacy'
    ]
    assert scan.dependencies[0].package_files == [str(library.resolve())]
    assert scan.dependencies[0].meta['resolved_path'] == str(library.resolve())


def test_single_project_discovers_referenced_vb6_project():
    scan = VB6Scanner().scan(
        EXAMPLE / 'Inventory.App' / 'Inventory.App.vbp'
    )[0]

    assert scan.moduleId == 'vb:InventoryApp'
    assert scan.dependencies[0].key == 'vb:InventoryCore'


def test_vb6_scanner_is_registered():
    scanner_classes = ts_scan.__get_pm_scanner_classes()

    assert VB6Scanner in scanner_classes
